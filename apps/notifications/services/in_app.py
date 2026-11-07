import logging
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.core.permissions import effective_role
from apps.notifications.models import Notification, NotificationRecipient, NotificationSource
from apps.notifications.permissions import ELIGIBLE_NOTIFICATION_ROLES

logger = logging.getLogger('notifications')
User = get_user_model()


class InAppNotificationService:
    """
    Service for dispatching in-app notifications to eligible dashboard users.
    Supports both user-composed notifications and system-generated administrative events.
    """

    @classmethod
    def send_notification(
        cls,
        title: str,
        message: str,
        recipients,
        sender=None,
        source_module: str = NotificationSource.DIRECT,
        source_id: str = '',
        data: dict = None,
        exclude_sender: bool = True
    ) -> Notification:
        """
        Dispatches a notification to the specified recipient users within an atomic transaction.
        """
        data = data or {}
        recipient_list = list(recipients)

        if exclude_sender and sender and sender in recipient_list:
            recipient_list.remove(sender)

        # Filter strictly for active, eligible notification roles
        valid_recipients = [
            u for u in recipient_list
            if u.is_active and effective_role(u) in ELIGIBLE_NOTIFICATION_ROLES
        ]

        if not valid_recipients:
            logger.info("InAppNotificationService: No valid eligible recipients for notification '%s'", title)
            return None

        with transaction.atomic():
            notification = Notification.objects.create(
                sender=sender,
                title=title,
                message=message,
                source_module=source_module,
                source_id=str(source_id) if source_id else '',
                data=data
            )

            recipient_objs = [
                NotificationRecipient(
                    notification=notification,
                    recipient=recipient_user,
                    is_read=False
                )
                for recipient_user in valid_recipients
            ]
            NotificationRecipient.objects.bulk_create(recipient_objs, ignore_conflicts=True)

        logger.info(
            "InAppNotificationService: Dispatched notification #%s to %d recipients (source: %s)",
            notification.id, len(recipient_objs), source_module
        )
        return notification

    @classmethod
    def send_system_notification(
        cls,
        title: str,
        message: str,
        source_module: str,
        source_id: str = '',
        data: dict = None,
        exclude_user=None,
        target_roles=None
    ) -> Notification:
        """
        Dispatches a system-generated notification to eligible dashboard users.
        Includes idempotency checking to prevent duplicate notifications for the same source.
        """
        data = data or {}
        target_roles = target_roles or ELIGIBLE_NOTIFICATION_ROLES

        # Prevent duplicate notifications for the exact same source event
        if source_id and source_module:
            existing = Notification.objects.filter(
                source_module=source_module,
                source_id=str(source_id),
                title=title
            ).first()
            if existing:
                logger.info(
                    "InAppNotificationService: Duplicate prevented for %s #%s ('%s')",
                    source_module, source_id, title
                )
                return existing

        recipient_qs = User.objects.filter(
            is_active=True,
            role__in=target_roles
        )

        if exclude_user:
            exclude_id = getattr(exclude_user, 'id', exclude_user)
            recipient_qs = recipient_qs.exclude(id=exclude_id)

        recipients = list(recipient_qs)
        if not recipients:
            logger.info(
                "InAppNotificationService: No eligible recipients found for system notification %s #%s",
                source_module, source_id
            )
            return None

        return cls.send_notification(
            title=title,
            message=message,
            recipients=recipients,
            sender=None,
            source_module=source_module,
            source_id=source_id,
            data=data,
            exclude_sender=False
        )

