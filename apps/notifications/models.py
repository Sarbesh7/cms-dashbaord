from django.conf import settings
from django.db import models
from apps.core.models import TimeStampModel


class DeviceTokenQuerySet(models.QuerySet):
    def active(self):
        """Return only device tokens that currently have push notifications enabled."""
        return self.filter(enabled=True)

    def for_user(self, user):
        """Return enabled device tokens associated with a specific user or user ID."""
        user_id = getattr(user, 'id', user)
        return self.filter(user_id=user_id, enabled=True)

    def for_platform(self, platform):
        """Return enabled device tokens for a specific platform ('android' or 'ios')."""
        if platform:
            return self.filter(platform=str(platform).lower().strip(), enabled=True)
        return self.none()


class DeviceTokenManager(models.Manager):
    def get_queryset(self):
        return DeviceTokenQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def for_platform(self, platform):
        return self.get_queryset().for_platform(platform)


class DeviceToken(TimeStampModel):
    class Platform(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'

    id = models.BigAutoField(primary_key=True)
    token = models.CharField(
        max_length=512,
        unique=True,
        db_index=True,
        help_text="Push notification device token issued by APNS or FCM."
    )
    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        db_index=True,
        help_text="Mobile operating system platform."
    )
    enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether push notifications are enabled for this device."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_tokens',
        help_text="Associated authenticated user account, if logged in."
    )

    objects = DeviceTokenManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'enabled'], name='devicetoken_user_enabled_idx'),
            models.Index(fields=['platform', 'enabled'], name='devicetoken_plat_enabled_idx'),
        ]

    def __str__(self):
        masked_token = f"{self.token[:8]}...{self.token[-6:]}" if len(self.token) > 14 else "***"
        status = "enabled" if self.enabled else "disabled"
        user_repr = self.user.username if self.user else "Guest"
        return f"DeviceToken({self.platform}, {status}, {user_repr}, {masked_token})"


# Model alias for Strapi naming compatibility
PushDevice = DeviceToken


class NotificationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent'
    PARTIALLY_SENT = 'partially_sent', 'Partially Sent'
    FAILED = 'failed', 'Failed'


class NotificationHistory(TimeStampModel):
    """
    Immutable historical snapshot of an outgoing push notification.
    Preserves title, body, and payload data even if source content is edited or deleted.
    """
    id = models.BigAutoField(primary_key=True)
    source_module = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Module that triggered the notification (e.g. 'announcement', 'notice')."
    )
    source_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Primary key or slug of source content."
    )
    source_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Snapshot of the source content title at send time."
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True, help_text="Navigation payload passed to the mobile client.")
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
        db_index=True
    )
    total_devices = models.PositiveIntegerField(default=0)
    accepted_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    retry_count = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source_module', 'status'], name='notif_mod_status_idx'),
            models.Index(fields=['status', 'created_at'], name='notif_status_created_idx'),
        ]

    def __str__(self):
        return f"NotificationHistory({self.id}, {self.source_module}, {self.status}, '{self.title[:30]}')"


class NotificationAttempt(models.Model):
    """
    Individual delivery attempt log for an outgoing notification.
    Preserves audit history across initial send and subsequent retries.
    """
    id = models.BigAutoField(primary_key=True)
    notification = models.ForeignKey(
        NotificationHistory,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    attempt_number = models.PositiveIntegerField(default=1)
    targeted_count = models.PositiveIntegerField(default=0)
    accepted_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=NotificationStatus.choices)
    error_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['attempt_number']

    def __str__(self):
        return f"NotificationAttempt({self.notification_id} #{self.attempt_number}, {self.status})"


class NotificationRecipientResult(models.Model):
    """
    Records per-device delivery outcome to allow safe, selective retries
    targeting only failed recipients without exposing raw tokens.
    """
    class ResultStatus(models.TextChoices):
        ACCEPTED = 'accepted', 'Accepted'
        FAILED = 'failed', 'Failed'
        INVALID = 'invalid', 'Invalid Token'

    id = models.BigAutoField(primary_key=True)
    notification = models.ForeignKey(
        NotificationHistory,
        on_delete=models.CASCADE,
        related_name='recipient_results'
    )
    device_token = models.ForeignKey(
        DeviceToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    status = models.CharField(max_length=20, choices=ResultStatus.choices)
    error_message = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('notification', 'device_token')

    def __str__(self):
        return f"RecipientResult({self.notification_id}, token_id={self.device_token_id}, {self.status})"


