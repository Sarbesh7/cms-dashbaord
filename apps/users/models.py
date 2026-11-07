
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Superadmin'),
        ('admin', 'Admin'),
        ('cms_user', 'Cms User'),
        ('operations', 'Operations'),
        ('papers', 'Papers'),
        ('notice', 'Notice'),
        ('blog', 'Blog'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cms_user')


class LoginAttempt(models.Model):
    ip_address = models.GenericIPAddressField(db_index=True)
    identifier = models.CharField(max_length=255, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    successful = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['identifier', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        status_str = "SUCCESS" if self.successful else "FAILED"
        return f"{self.timestamp} - {self.ip_address} - {self.identifier} ({status_str})"
  


