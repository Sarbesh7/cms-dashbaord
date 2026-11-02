import os
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from apps.core.models import TimeStampModel


def validate_file_size(value):
    limit = 5 * 1024 * 1024  # 5 MB Limit
    if value.size > limit:
        raise ValidationError('File too large. Size should not exceed 5 MB.')


@deconstructible
class SecureFilePath:
    def __init__(self, folder_name):
        self.folder_name = folder_name

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()
        secure_name = f"{uuid.uuid4()}{ext}"
        return os.path.join(self.folder_name, secure_name)


class Announcement(TimeStampModel):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.FileField(
        upload_to=SecureFilePath('announcements/'),
        validators=[validate_file_size],
        null=True,
        blank=True
    )
    link = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
