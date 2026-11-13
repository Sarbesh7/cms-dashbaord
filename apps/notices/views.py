import logging

from django.http import Http404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.activity_logging import diff_snapshots, log_activity, model_snapshot
from apps.core.cache import versioned_cache_page
from apps.core.ordering import apply_ordering
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasModulePermission
from apps.core.publishing import TRANSITION_VERBS, check_publish_permission, publish_transition
from apps.core.visibility import PUBLISHED, can_view_private
from apps.notifications.services.in_app import InAppNotificationService
from .models import Notice
from .serializers import NoticeSerializer

logger = logging.getLogger('notice')

NOTICE_ORDERING = {"id": "id", "title": "title", "category": "category", "status": "status",
                   "createdAt": "created_at", "created_at": "created_at"}


class _NoticeView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_module = "notices"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), HasModulePermission("notices")]


class NoticeListView(_NoticeView):

    @versioned_cache_page(60 * 5)
    def get(self, request):
        notices = Notice.objects.all()
        if not can_view_private(request, "notices"):
            notices = notices.filter(status=PUBLISHED)

        search = request.query_params.get('search') or request.query_params.get('name') or request.query_params.get('title')
        status_filter = request.query_params.get('status')
        category_filter = request.query_params.get('category')
        id_filter = request.query_params.get('id')
        date_filter = request.query_params.get('date')

        try:
            if id_filter:
                notices = notices.filter(id=int(id_filter))
            if date_filter:
                notices = notices.filter(created_at__date=date_filter)
        except Exception:
            return Response({"detail": "Invalid filter value."}, status=status.HTTP_400_BAD_REQUEST)
        if search:
            notices = notices.filter(title__icontains=search)
        if status_filter:
            notices = notices.filter(status=status_filter)
        if category_filter:
            notices = notices.filter(category=category_filter)

        notices = apply_ordering(notices, request.query_params.get("ordering"), NOTICE_ORDERING, "-created_at")
        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(notices, request)
        return paginator.get_paginated_response(NoticeSerializer(result_page, many=True).data)

    def post(self, request):
        transition, denied = check_publish_permission(request, "notices", None, request.data.get("status"))
        if denied:
            return denied
        serializer = NoticeSerializer(data=request.data)
        if serializer.is_valid():
            notice = serializer.save()
            logger.info(f"Notice '{notice.title}' created by user id {request.user.pk}")
            log_activity(request, action="create", module="notices", target_id=notice.id, target_repr=notice.title,
                         description=f"Created notice '{notice.title}'")
            if transition == "publish":
                log_activity(request, action="publish", module="notices", target_id=notice.id,
                             target_repr=notice.title, description=f"Published notice '{notice.title}'")
                InAppNotificationService.send_system_notification(
                    title=f"Published Notice: {notice.title}",
                    message=(notice.description[:200] if notice.description else f"Notice '{notice.title}' has been published."),
                    source_module="notice",
                    source_id=str(notice.id),
                    data={
                        "type": "notice",
                        "noticeId": notice.slug or str(notice.id),
                    },
                    exclude_user=request.user,
                )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed notice creation. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NoticeDetailView(_NoticeView):

    def get_object(self, slug, public=False):
        qs = Notice.objects.filter(status=PUBLISHED) if public else Notice.objects.all()
        # Try slug first (covers numeric slugs)
        obj = qs.filter(slug=slug).first()
        if not obj and str(slug).isdigit():
            obj = qs.filter(id=int(slug)).first()
        if not obj:
            raise Http404
        return obj

    @versioned_cache_page(60 * 5)
    def get(self, request, slug):
        notice = self.get_object(slug, public=not can_view_private(request, "notices"))
        return Response(NoticeSerializer(notice).data)

    def _update(self, request, slug, partial):
        notice = self.get_object(slug)
        old_status = notice.status
        new_status = request.data.get("status", old_status if partial else None)
        transition, denied = check_publish_permission(request, "notices", old_status, new_status)
        if denied:
            return denied
        before = model_snapshot(notice)
        serializer = NoticeSerializer(notice, data=request.data, partial=partial)
        if serializer.is_valid():
            notice = serializer.save()
            changes = diff_snapshots(before, model_snapshot(notice))
            transition = publish_transition(old_status, notice.status)
            logger.info(f"Notice '{notice.title}' updated by user id {request.user.pk}")
            log_activity(request, action=transition or "update", module="notices", target_id=notice.id,
                         target_repr=notice.title,
                         description=f"{TRANSITION_VERBS[transition]} notice '{notice.title}'",
                         changes=changes)
            if transition == "publish":
                InAppNotificationService.send_system_notification(
                    title=f"Published Notice: {notice.title}",
                    message=(notice.description[:200] if notice.description else f"Notice '{notice.title}' has been published."),
                    source_module="notice",
                    source_id=str(notice.id),
                    data={
                        "type": "notice",
                        "noticeId": notice.slug or str(notice.id),
                    },
                    exclude_user=request.user,
                )
            return Response(serializer.data)
        logger.warning(f"Failed update for notice '{slug}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, slug):
        return self._update(request, slug, partial=False)

    def patch(self, request, slug):
        return self._update(request, slug, partial=True)

    def delete(self, request, slug):
        notice = self.get_object(slug)
        notice_id, notice_title = notice.id, notice.title
        notice.delete()
        logger.info(f"Notice '{notice_title}' deleted by user id {request.user.pk}")
        log_activity(request, action="delete", module="notices", target_id=notice_id, target_repr=notice_title,
                     description=f"Deleted notice '{notice_title}'")
        return Response(status=status.HTTP_204_NO_CONTENT)
