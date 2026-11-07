import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.activity_logging import diff_snapshots, log_activity, model_snapshot
from apps.core.ordering import apply_ordering
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasModulePermission
from apps.notifications.services.in_app import InAppNotificationService
from .models import Announcement
from .serializers import AnnouncementSerializer

logger = logging.getLogger('announcements')

ANNOUNCEMENT_ORDERING = {
    "id": "id",
    "title": "title",
    "createdAt": "created_at",
    "created_at": "created_at",
    "updatedAt": "updated_at",
    "updated_at": "updated_at",
}


class _AnnouncementView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_module = "announcements"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), HasModulePermission("announcements")()]


class AnnouncementListView(_AnnouncementView):
    def get(self, request):
        queryset = Announcement.objects.all()
        search = request.query_params.get('search') or request.query_params.get('title')
        if search:
            queryset = queryset.filter(title__icontains=search.strip())

        queryset = apply_ordering(queryset, request.query_params.get("ordering"), ANNOUNCEMENT_ORDERING, "-created_at")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AnnouncementSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = AnnouncementSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        announcement = serializer.save()
        logger.info(f"Announcement '{announcement.title}' created by user id {request.user.pk}")

        log_activity(
            request=request,
            action="create",
            module="announcements",
            target_id=str(announcement.id),
            target_repr=announcement.title,
            description=f"Created announcement '{announcement.title}'",
        )

        # Trigger in-app notification dispatch for eligible dashboard users
        InAppNotificationService.send_system_notification(
            title=f"New Announcement: {announcement.title}",
            message=announcement.description or f"Announcement '{announcement.title}' has been posted.",
            source_module="announcement",
            source_id=str(announcement.id),
            data={
                "type": "announcement",
                "id": announcement.id,
                "link": announcement.link or "",
            },
            exclude_user=request.user,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AnnouncementDetailView(_AnnouncementView):
    def get(self, request, pk):
        announcement = get_object_or_404(Announcement, pk=pk)
        serializer = AnnouncementSerializer(announcement, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _update(self, request, pk, partial):
        announcement = get_object_or_404(Announcement, pk=pk)
        before = model_snapshot(announcement)
        serializer = AnnouncementSerializer(announcement, data=request.data, partial=partial, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        announcement = serializer.save()
        changes = diff_snapshots(before, model_snapshot(announcement))
        logger.info(f"Announcement '{announcement.title}' updated by user id {request.user.pk}")

        log_activity(
            request=request,
            action="update",
            module="announcements",
            target_id=str(announcement.id),
            target_repr=announcement.title,
            description=f"Updated announcement '{announcement.title}'",
            changes=changes,
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def delete(self, request, pk):
        announcement = get_object_or_404(Announcement, pk=pk)
        ann_id, ann_title = announcement.id, announcement.title
        announcement.delete()
        logger.info(f"Announcement '{ann_title}' deleted by user id {request.user.pk}")

        log_activity(
            request=request,
            action="delete",
            module="announcements",
            target_id=str(ann_id),
            target_repr=ann_title,
            description=f"Deleted announcement '{ann_title}'",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
