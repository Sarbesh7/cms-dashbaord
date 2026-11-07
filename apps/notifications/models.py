from django.conf import settings
from django.db import models
from apps.core.models import TimeStampModel


class NotificationSource(models.TextChoices):
    DIRECT = 'direct', 'Direct'
    ANNOUNCEMENT = 'announcement', 'Announcement'
    NOTICE = 'notice', 'Notice'
    MEMBER = 'member', 'Member'
    CERTIFICATE = 'certificate', 'Certificate'
    SYSTEM = 'system', 'System'


class Notification(TimeStampModel):
    """
    Core immutable in-app notification record.
    Represents an announcement, alert, or direct message composed by a user or system event.
    """
    id = models.BigAutoField(primary_key=True)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications',
        help_text="User who composed the notification. Null for system-generated notifications."
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    source_module = models.CharField(
        max_length=50,
        choices=NotificationSource.choices,
        default=NotificationSource.DIRECT,
        db_index=True,
        help_text="Origin module or context of the notification."
    )
    source_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Reference ID (e.g. primary key or slug) of the associated source object."
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional structured metadata or navigation links."
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', '-created_at'], name='notif_sender_created_idx'),
            models.Index(fields=['source_module', 'source_id'], name='notif_source_idx'),
        ]

    def __str__(self):
        sender_str = self.sender.username if self.sender else "System"
        return f"Notification({self.id}, {sender_str}, '{self.title[:30]}')"


class NotificationRecipient(models.Model):
    """
    Per-recipient delivery and read/unread status tracking for a notification.
    """
    id = models.BigAutoField(primary_key=True)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_notifications'
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this notification has been marked read by the recipient."
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the notification was marked as read."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('notification', 'recipient')
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at'], name='notif_recip_read_idx'),
            models.Index(fields=['recipient', '-created_at'], name='notif_recip_created_idx'),
        ]

    def __str__(self):
        status = "Read" if self.is_read else "Unread"
        return f"NotificationRecipient({self.notification_id} -> {self.recipient.username}: {status})"
