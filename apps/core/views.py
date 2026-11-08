from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.core.activity_logging import log_activity
from apps.core.dashboard import activity_log_summary, build_overview
from apps.core.media import MediaError, delete_asset, find_references, normalize_public_id, visible_references
from apps.core.pagination import StandardPagination
from apps.core.permissions import CanViewActivityLogs, HasPermission
from .models import ActivityLog
from .serializers import ActivityLogSerializer


class DashboardOverviewView(APIView):
    """
    Role-aware dashboard overview: per-module statistics (database aggregation)
    and the latest records, limited to modules the authenticated user can view.
    Restricted modules are omitted from the response entirely.
    """
    permission_classes = [IsAuthenticated, HasPermission("dashboard.overview.view")]

    def get(self, request):
        response = Response(build_overview(request.user))
        response["Cache-Control"] = "private, no-store"
        return response


ACTIVITY_LOG_ORDERING = {
    "timestamp": "timestamp", "-timestamp": "-timestamp",
    "actor": "actor_name_snapshot", "-actor": "-actor_name_snapshot",
    "action": "action", "-action": "-action",
    "module": "module", "-module": "-module",
    "record": "target_repr", "-record": "-target_repr",
}


class ActivityLogListView(APIView):
    """
    Read-only audit log endpoint restricted to superadmin and admin.
    Append-only: mutations are rejected with 405 Method Not Allowed.
    """
    permission_classes = [IsAuthenticated, CanViewActivityLogs]
    pagination_class = StandardPagination

    def get(self, request):
        qs = ActivityLog.objects.select_related('user').all()

        module = request.query_params.get('module')
        action = request.query_params.get('action')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        search = request.query_params.get('search')
        actor = request.query_params.get('actor')
        record = request.query_params.get('record')

        if module:
            qs = qs.filter(module__iexact=module)
        if action:
            qs = qs.filter(action__iexact=action)
        try:
            if start_date:
                qs = qs.filter(timestamp__date__gte=start_date)
            if end_date:
                qs = qs.filter(timestamp__date__lte=end_date)
        except Exception:
            return Response({"detail": "Invalid date filter."}, status=status.HTTP_400_BAD_REQUEST)
        if actor:
            qs = qs.filter(
                Q(actor_name_snapshot__icontains=actor) |
                Q(actor_username_snapshot__icontains=actor) |
                Q(user_email_snapshot__icontains=actor)
            )
        if record:
            qs = qs.filter(Q(target_repr__icontains=record) | Q(target_id__iexact=record))
        if search:
            qs = qs.filter(
                Q(target_repr__icontains=search) |
                Q(user_email_snapshot__icontains=search) |
                Q(actor_name_snapshot__icontains=search) |
                Q(actor_username_snapshot__icontains=search) |
                Q(target_id__icontains=search) |
                Q(description__icontains=search) |
                Q(action__icontains=search) |
                Q(module__icontains=search)
            )

        ordering = ACTIVITY_LOG_ORDERING.get(request.query_params.get('ordering') or "-timestamp", "-timestamp")
        qs = qs.order_by(ordering, "-id")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ActivityLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ActivityLogSummaryView(APIView):
    """Summary cards: total activities, logins this week, mutations today, most active module."""
    permission_classes = [IsAuthenticated, CanViewActivityLogs]

    def get(self, request):
        return Response(activity_log_summary())


class ActivityLogDetailView(APIView):
    """Read-only detail view for an individual activity log record."""
    permission_classes = [IsAuthenticated, CanViewActivityLogs]

    def get(self, request, pk):
        try:
            log = ActivityLog.objects.select_related('user').get(pk=pk)
        except ActivityLog.DoesNotExist:
            return Response({"detail": "Activity log not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ActivityLogSerializer(log).data)


class MediaThrottle(UserRateThrottle):
    scope = "media"


class MediaUsageView(APIView):
    """GET /api/v1/media/usage/?public_id=...&url=... -> records still using the asset."""
    permission_classes = [IsAuthenticated, HasPermission("media.view")]

    def get(self, request):
        public_id = request.query_params.get("public_id") or ""
        url = request.query_params.get("url") or ""
        if not public_id and not url:
            return Response({"detail": "public_id or url is required."}, status=status.HTTP_400_BAD_REQUEST)
        if public_id:
            try:
                public_id = normalize_public_id(public_id)
            except MediaError as exc:
                return Response({"detail": exc.message}, status=exc.status_code)
        refs = find_references(public_id=public_id or None, url=url or None,
                               exclude_blog_id=request.query_params.get("exclude_blog_id"))
        return Response({"in_use": bool(refs), "references": visible_references(refs, request.user)})


class MediaDeleteView(APIView):
    """POST /api/v1/media/delete/ {public_id, exclude_blog_id?} -> delete an unreferenced asset."""
    permission_classes = [IsAuthenticated, HasPermission("media.delete")]
    throttle_classes = [MediaThrottle]

    def post(self, request):
        public_id = str(request.data.get("public_id") or "")
        try:
            module = delete_asset(request.user, public_id, exclude_blog_id=request.data.get("exclude_blog_id"),
                                  url=str(request.data.get("url") or "") or None)
        except MediaError as exc:
            body = {"detail": exc.message}
            if exc.references:
                body["references"] = exc.references
            return Response(body, status=exc.status_code)
        log_activity(request, action="media_delete", module="media", target_id=public_id, target_repr=public_id,
                     description=f"Deleted unused {module} media asset", details={"owner_module": module})
        return Response({"detail": "Asset permanently deleted from media storage."}, status=status.HTTP_200_OK)
