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


class Event(TimeStampModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    
    # Securely point to events_templates subfolder
    image = models.FileField(
        upload_to=SecureFilePath('events_templates/'),
        validators=[validate_file_size],
        null=True,
        blank=True
    )
    
    date = models.DateTimeField()
    registration_link = models.URLField(blank=True, null=True)
    mentors = models.ManyToManyField('Mentor', related_name='events', blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('published', 'Published'),  
            ('completed', 'Completed')
        ],
        default='draft'
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class Mentor(TimeStampModel):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    expertise = models.CharField(max_length=200)
    linkedin_profile = models.URLField(blank=True, null=True)
    
    # Securely point to mentors_photos subfolder
    photo = models.ImageField(
        upload_to=SecureFilePath('mentors_photos/'),
        validators=[validate_file_size],
        null=True,
        blank=True
    )
    slug = models.SlugField(unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)