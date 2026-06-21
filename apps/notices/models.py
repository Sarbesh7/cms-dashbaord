import os
import uuid
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampModel
from django.utils.deconstruct import deconstructible


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
 
 
class Notice(TimeStampModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, null=True, db_index=True)
    description = models.TextField()
    
   
    image = models.FileField(
        upload_to=SecureFilePath('notices/'), 
        validators=[validate_file_size],
        null=True, 
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('published', 'Published')
        ],
        default='draft',
        null=True,
        blank=True
    )

    category = models.CharField(
        max_length=50,
        choices=[
            ('administrative', 'Administrative'),
            ('academic', 'Academic'),
            ('events', 'Events')
        ],
        null=True,
        blank=True
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)