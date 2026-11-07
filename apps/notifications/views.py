import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core.pagination import StandardPagination
from .models import Notification, NotificationRecipient
from .permissions import IsEligibleNotificationUser, ELIGIBLE_NOTIFICATION_ROLES
from .serializers import (
    NotificationRecipientInboxSerializer,
    NotificationSentSerializer,
    NotificationComposeSerializer,
    EligibleRecipientSerializer,
)
from .services.in_app import InAppNotificationService

logger = logging.getLogger('notifications')
User = get_user_model()


class NotificationInboxListView(APIView):
    """
    Lists notifications received by the authenticated eligible user.
    Supports filtering by read/unread status, source module, and search keyword.
    """
    permission_classes = [IsEligibleNotificationUser]
    pagination_class = StandardPagination

    def get(self, request):
        user = request.user
        queryset = (
            NotificationRecipient.objects
            .filter(recipient=user)
            .select_related('notification', 'notification__sender')
            .order_by('-created_at')
        )

        # Filter by read status
        is_read_param = request.query_params.get('is_read')
        if is_read_param is not None and is_read_param != '' and is_read_param.lower() != 'all':
            if is_read_param.lower() in ('true', '1'):
                queryset = queryset.filter(is_read=True)
            elif is_read_param.lower() in ('false', '0'):
                queryset = queryset.filter(is_read=False)

        # Filter by source module
        source_module = request.query_params.get('source_module')
        if source_module and source_module.lower() != 'all':
            queryset = queryset.filter(notification__source_module=source_module.strip())

        # Search by title or message
        search_query = request.query_params.get('search')
        if search_query:
            q = search_query.strip()
            queryset = queryset.filter(
                Q(notification__title__icontains=q) |
                Q(notification__message__icontains=q) |
                Q(notification__sender__username__icontains=q) |
                Q(notification__sender__first_name__icontains=q) |
                Q(notification__sender__last_name__icontains=q)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = NotificationRecipientInboxSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class NotificationUnreadCountView(APIView):
    """
    Returns the count of unread notifications for the current authenticated user.
    """
    permission_classes = [IsEligibleNotificationUser]

    def get(self, request):
        count = NotificationRecipient.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return Response({"unread_count": count})


class NotificationMarkAllReadView(APIView):
    """
    Marks all received notifications for the current user as read.
    """
    permission_classes = [IsEligibleNotificationUser]

    def post(self, request):
        now = timezone.now()
        updated = NotificationRecipient.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True, read_at=now)

        return Response({
            "message": f"Marked {updated} notification(s) as read.",
            "marked_count": updated
        })


class NotificationToggleReadView(APIView):
    """
    Marks an individual received notification as read or unread for the current user.
    """
    permission_classes = [IsEligibleNotificationUser]

    def post(self, request, pk):
        recipient_record = get_object_or_404(
            NotificationRecipient,
            pk=pk,
            recipient=request.user
        )

        desired_read = request.data.get('is_read')
        if desired_read is None:
            # Toggle if not explicitly specified
            recipient_record.is_read = not recipient_record.is_read
        elif isinstance(desired_read, str):
            recipient_record.is_read = desired_read.strip().lower() in ('true', '1')
        else:
            recipient_record.is_read = bool(desired_read)

        recipient_record.read_at = timezone.now() if recipient_record.is_read else None
        recipient_record.save(update_fields=['is_read', 'read_at'])

        return Response({
            "id": recipient_record.id,
            "is_read": recipient_record.is_read,
            "read_at": recipient_record.read_at,
            "message": "Notification marked as read." if recipient_record.is_read else "Notification marked as unread."
        })


class NotificationComposeView(APIView):
    """
    Composes and dispatches a notification to selected eligible users or all eligible users.
    """
    permission_classes = [IsEligibleNotificationUser]

    def post(self, request):
        serializer = NotificationComposeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        recipients = data['resolved_recipients']

        notification = InAppNotificationService.send_notification(
            title=data['title'],
            message=data['message'],
            recipients=recipients,
            sender=request.user,
            exclude_sender=True
        )

        if not notification:
            return Response(
                {"error": "Failed to dispatch notification. No valid eligible recipients found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "message": f"Notification successfully sent to {len(recipients)} recipient(s).",
                "id": notification.id
            },
            status=status.HTTP_201_CREATED
        )


class NotificationSentListView(APIView):
    """
    Lists notifications sent by the current authenticated user.
    """
    permission_classes = [IsEligibleNotificationUser]
    pagination_class = StandardPagination

    def get(self, request):
        queryset = (
            Notification.objects
            .filter(sender=request.user)
            .prefetch_related('recipients__recipient')
            .order_by('-created_at')
        )

        search_query = request.query_params.get('search')
        if search_query:
            q = search_query.strip()
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(message__icontains=q)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = NotificationSentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class EligibleRecipientsListView(APIView):
    """
    Returns the list of dashboard users who are eligible to receive notifications
    (Superadmin, Admin, and CMS Users). Excludes the requesting user.
    """
    permission_classes = [IsEligibleNotificationUser]

    def get(self, request):
        users = (
            User.objects
            .filter(is_active=True, role__in=ELIGIBLE_NOTIFICATION_ROLES)
            .exclude(id=request.user.id)
            .order_by('first_name', 'last_name', 'username')
        )
        serializer = EligibleRecipientSerializer(users, many=True)
        return Response(serializer.data)
