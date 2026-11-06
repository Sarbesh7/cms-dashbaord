from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import DeviceToken
from .serializers import (
    DeviceTokenSerializer,
    DeviceTokenRegistrationSerializer,
    DeviceTokenStatusSerializer,
    DeviceTokenUpdateSerializer,
    PushDeviceRegisterSerializer,
    PushDeviceUnregisterSerializer,
)



class IsDeviceTokenOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission:
    - Superadmins and Admins can access any device token record.
    - Authenticated users can only access their own device tokens.
    - Unauthenticated guest tokens can only be updated/read by admins or guest clients.
    """

    def has_object_permission(self, request, view, obj):
        # Admin / Superadmin override
        if request.user.is_authenticated and getattr(request.user, 'role', '') in ('superadmin', 'admin'):
            return True

        # Token owned by an authenticated user
        if obj.user_id is not None:
            return request.user.is_authenticated and obj.user_id == request.user.id

        # Guest token (user is None)
        # Regular authenticated users cannot hijack guest tokens unless they re-register them
        if request.user.is_authenticated:
            return False

        # Anonymous caller accessing guest token
        return True


class DeviceTokenListCreateView(APIView):
    """
    POST /api/v1/device-tokens/
    Register a new device token or idempotently update an existing token.

    GET /api/v1/device-tokens/
    List device tokens. Authenticated users see only their own devices. Admins can see all devices.
    """
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def post(self, request):
        serializer = DeviceTokenRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user if request.user.is_authenticated else None
        device_token, created = serializer.save(user=user)

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        message = "Device token registered successfully." if created else "Device token updated successfully."

        return Response(
            {
                "success": True,
                "message": message,
                "data": {
                    "id": device_token.id,
                    "platform": device_token.platform,
                    "enabled": device_token.enabled,
                },
            },
            status=status_code,
        )

    def get(self, request):
        user = request.user
        is_admin = getattr(user, 'role', '') in ('superadmin', 'admin')

        if is_admin:
            queryset = DeviceToken.objects.all().select_related('user')
        else:
            queryset = DeviceToken.objects.filter(user=user)

        # Optional query filters
        platform = request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(platform=platform.lower().strip())

        enabled_param = request.query_params.get('enabled')
        if enabled_param is not None:
            if enabled_param.lower() in ('true', '1'):
                queryset = queryset.filter(enabled=True)
            elif enabled_param.lower() in ('false', '0'):
                queryset = queryset.filter(enabled=False)

        serializer = DeviceTokenSerializer(queryset, many=True)
        return Response(
            {
                "success": True,
                "count": queryset.count(),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class DeviceTokenStatusView(APIView):
    """
    PATCH /api/v1/device-tokens/{id}/status/
    Update only the push notification enabled status for a device.
    """
    permission_classes = [IsDeviceTokenOwnerOrAdmin]

    def patch(self, request, pk):
        device_token = get_object_or_404(DeviceToken, pk=pk)
        self.check_object_permissions(request, device_token)

        serializer = DeviceTokenStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.update(device_token, serializer.validated_data)

        action_word = "enabled" if device_token.enabled else "disabled"
        return Response(
            {
                "success": True,
                "message": f"Push notifications {action_word} successfully.",
                "data": {
                    "id": device_token.id,
                    "enabled": device_token.enabled,
                },
            },
            status=status.HTTP_200_OK,
        )


class DeviceTokenDetailView(APIView):
    """
    GET /api/v1/device-tokens/{id}/
    Retrieve device token metadata.

    PATCH /api/v1/device-tokens/{id}/
    Update token value or platform when refreshed.

    DELETE /api/v1/device-tokens/{id}/
    Unregister a device token.
    """
    permission_classes = [IsDeviceTokenOwnerOrAdmin]

    def get(self, request, pk):
        device_token = get_object_or_404(DeviceToken, pk=pk)
        self.check_object_permissions(request, device_token)

        serializer = DeviceTokenSerializer(device_token)
        return Response(
            {
                "success": True,
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        device_token = get_object_or_404(DeviceToken, pk=pk)
        self.check_object_permissions(request, device_token)

        serializer = DeviceTokenUpdateSerializer(device_token, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(
            {
                "success": True,
                "message": "Device token updated successfully.",
                "data": {
                    "id": device_token.id,
                    "platform": device_token.platform,
                    "enabled": device_token.enabled,
                },
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        device_token = get_object_or_404(DeviceToken, pk=pk)
        self.check_object_permissions(request, device_token)

        device_token.delete()
        return Response(
            {
                "success": True,
                "message": "Device token unregistered successfully.",
            },
            status=status.HTTP_204_NO_CONTENT,
        )


class PushDeviceRegisterView(APIView):
    """
    POST /api/push-devices/register
    Public endpoint for mobile apps to register or re-enable Expo push tokens.
    Strictly adheres to legacy mobile contract and Strapi JSON response format.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PushDeviceRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            first_error = "Validation error"
            for field, errs in serializer.errors.items():
                if errs:
                    first_error = errs[0] if isinstance(errs, list) else str(errs)
                    break
            return Response(
                {"error": first_error, "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = serializer.validated_data['token']
        platform = serializer.validated_data['platform']

        try:
            device = DeviceToken.objects.filter(token=token).first()
            if device:
                # Re-enable if disabled, or update platform
                if not device.enabled or device.platform != platform:
                    device.enabled = True
                    device.platform = platform
                    device.save(update_fields=['enabled', 'platform', 'updated_at'])

                return Response(
                    {
                        "success": True,
                        "registered": False,
                        "message": "Device already registered",
                    },
                    status=status.HTTP_200_OK,
                )

            # Register new device
            DeviceToken.objects.create(
                token=token,
                platform=platform,
                enabled=True,
                user=None,
            )

            return Response(
                {
                    "success": True,
                    "registered": True,
                    "message": "Device registered successfully",
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"error": "Unable to register device", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PushDeviceUnregisterView(APIView):
    """
    POST /api/push-devices/unregister
    Public endpoint for mobile apps to disable Expo push tokens (opt-out).
    The token record is preserved with enabled=False.
    Idempotent: unknown or already disabled tokens return 200 OK.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PushDeviceUnregisterSerializer(data=request.data)
        if not serializer.is_valid():
            first_error = "Push token is required"
            for field, errs in serializer.errors.items():
                if errs:
                    first_error = errs[0] if isinstance(errs, list) else str(errs)
                    break
            return Response(
                {"error": first_error, "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = serializer.validated_data['token']

        try:
            device = DeviceToken.objects.filter(token=token).first()
            if device and device.enabled:
                device.enabled = False
                device.save(update_fields=['enabled', 'updated_at'])

            return Response(
                {
                    "success": True,
                    "message": "Device unregistered",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": "Unable to unregister device", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class NotificationHistoryListView(APIView):
    """
    GET /api/v1/notifications/
    Lists outgoing push notifications with filtering by status, source_module, date, and title search.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        from apps.core.permissions import HasPermission
        return [permissions.IsAuthenticated(), HasPermission("notifications.view")()]

    def get(self, request):
        from apps.core.pagination import StandardPagination
        from .models import NotificationHistory
        from .serializers import NotificationHistorySerializer

        queryset = NotificationHistory.objects.all().prefetch_related('attempts')

        source_module = request.query_params.get('source_module')
        if source_module and source_module.lower() != 'all':
            queryset = queryset.filter(source_module=source_module.lower())

        status_param = request.query_params.get('status')
        if status_param and status_param.lower() != 'all':
            queryset = queryset.filter(status=status_param.lower())

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(title__icontains=search.strip())

        date_param = request.query_params.get('date')
        if date_param:
            queryset = queryset.filter(created_at__date=date_param)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = NotificationHistorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class NotificationHistoryDetailView(APIView):
    """
    GET /api/v1/notifications/{id}/
    Retrieves full details of an outgoing notification including complete attempt logs.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        from apps.core.permissions import HasPermission
        return [permissions.IsAuthenticated(), HasPermission("notifications.view")()]

    def get(self, request, pk):
        from .models import NotificationHistory
        from .serializers import NotificationHistorySerializer

        notification = get_object_or_404(NotificationHistory.objects.prefetch_related('attempts'), pk=pk)
        serializer = NotificationHistorySerializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationRetryView(APIView):
    """
    POST /api/v1/notifications/{id}/retry/
    Retries failed recipients for an existing notification.
    Targeting only previously failed devices; does not resend to already accepted devices.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        from apps.core.permissions import HasPermission
        return [permissions.IsAuthenticated(), HasPermission("notifications.retry")()]

    def post(self, request, pk):
        from apps.core.activity_logging import log_activity
        from .models import NotificationHistory
        from .serializers import NotificationHistorySerializer
        from .services.push import PushNotificationService

        notification = get_object_or_404(NotificationHistory, pk=pk)

        if notification.failed_count == 0:
            return Response(
                {"error": "This notification has no failed recipients eligible for retry."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_history = PushNotificationService.dispatch_notification(
            title=notification.title,
            body=notification.body,
            source_module=notification.source_module,
            source_id=notification.source_id,
            source_title=notification.source_title,
            data=notification.data,
            existing_history=notification,
            is_retry=True,
        )

        log_activity(
            request=request,
            action="retry",
            module="notifications",
            target_id=str(notification.id),
            target_repr=f"Notification #{notification.id}: {notification.title[:50]}",
            description=f"User {request.user.username} retried push notification for {notification.source_module} '{notification.source_title}'",
            details={
                "retry_count": updated_history.retry_count,
                "status": updated_history.status,
                "accepted_count": updated_history.accepted_count,
                "failed_count": updated_history.failed_count,
            }
        )

        serializer = NotificationHistorySerializer(updated_history)
        return Response(
            {
                "success": True,
                "message": f"Retry completed. Current status: {updated_history.status}",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


