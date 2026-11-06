from django.conf import settings
from django.db import models


class TimeStampModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ImmutableLogError(Exception):
    """Raised when code tries to modify or delete an activity log entry."""


class ActivityLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        # The only permitted write: Django's SET_NULL when the actor account is deleted.
        if kwargs == {"user": None}:
            return super().update(**kwargs)
        raise ImmutableLogError("Activity logs are append-only and cannot be updated.")

    def delete(self):
        raise ImmutableLogError("Activity logs are append-only and cannot be deleted.")


class ActivityLog(models.Model):
    # The FK is only a convenience link; every actor detail is snapshotted so the
    # entry survives (unchanged) when the account is deleted (FK -> NULL).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs"
    )
    actor_id_snapshot = models.BigIntegerField(null=True, blank=True)
    actor_name_snapshot = models.CharField(max_length=255, blank=True)
    user_email_snapshot = models.EmailField(max_length=255, blank=True)
    user_role_snapshot = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    # {"field": {"before": ..., "after": ...}} for updates; never contains secrets.
    changes = models.JSONField(default=dict, blank=True)
    action = models.CharField(max_length=50, db_index=True)  # create, update, delete, publish, unpublish, login, logout, password_change
    module = models.CharField(max_length=50, db_index=True)  # notices, events, tenure, certificates, papers, blogs, users, auth, media
    target_id = models.CharField(max_length=255, blank=True)
    target_repr = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)  # stored in UTC (USE_TZ)

    objects = ActivityLogQuerySet.as_manager()

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableLogError("Activity logs are append-only and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLogError("Activity logs are append-only and cannot be deleted.")

    def __str__(self):
        return f"[{self.module.upper()}] {self.action} by {self.user_email_snapshot or self.user or 'System'} at {self.timestamp}"