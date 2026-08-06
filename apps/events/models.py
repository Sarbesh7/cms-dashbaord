import os
import uuid
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from apps.core.models import TimeStampModel
from apps.tenure.models import Member, Tenure


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


class Mentor(TimeStampModel):
    # Optional link to an internal team member from tenure
    member = models.ForeignKey(
        Member, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='mentor_profiles',
        help_text="Select an existing team member, or leave blank for guest/external mentors."
    )
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True, null=True)
    expertise = models.CharField(max_length=200)
    linkedin_profile = models.URLField(blank=True, null=True)
    photo = models.ImageField(
        upload_to=SecureFilePath('mentors_photos/'),
        validators=[validate_file_size],
        null=True,
        blank=True
    )
    slug = models.SlugField(unique=True, blank=True, db_index=True)

    def __str__(self):
        return self.name or (self.member.name if self.member else "Unnamed Mentor")

    def save(self, *args, **kwargs):
        # Auto-populate name, email, and photo from Member if linked
        if self.member:
            if not self.name:
                self.name = self.member.name
            if not self.email:
                self.email = self.member.email
            if not self.photo and self.member.image:
                self.photo = self.member.image
                
        if not self.slug and self.name:
            base_slug = slugify(self.name)
            slug = base_slug
            count = 1
            while Mentor.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{count}"
                count += 1
            self.slug = slug

        super().save(*args, **kwargs)


class Event(TimeStampModel):
    class Category(models.TextChoices):
        WORKSHOP = 'workshop', 'Workshop'
        SEMINAR = 'seminar', 'Seminar'
        CONFERENCE = 'conference', 'Conference'
        WEBINAR = 'webinar', 'Webinar'
        HACKATHON = 'hackathon', 'Hackathon'
        BOOTCAMP = 'bootcamp', 'Bootcamp'
        TALK = 'talk', 'Talk'
        MOCK_TEST = 'mocktest', 'Mock Test'
        OTHER = 'other', 'Other'

    class Tag(models.TextChoices):
        WEB = 'web', 'Web'
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        FRONTEND = 'frontend', 'Front-End'
        BACKEND = 'backend', 'Back-End'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        COMPLETED = 'completed', 'Completed'

    tenure = models.ForeignKey(
        Tenure, 
        on_delete=models.CASCADE, 
        related_name='events', 
        null=True, 
        blank=True
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, db_index=True)
    description = models.TextField()
    organiser = models.CharField(max_length=200, blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    
    image = models.FileField(
        upload_to=SecureFilePath('events_templates/'),
        validators=[validate_file_size],
        null=True,
        blank=True
    )
    
    date = models.DateTimeField()
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    
    available_seats = models.PositiveIntegerField(default=0)
    registration_fee_bmc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    registration_fee_non_bmc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    registration_link = models.URLField(blank=True, null=True)
    
    category = models.CharField(max_length=50, choices=Category.choices, null=True, blank=True)
    tags = models.CharField(max_length=50, choices=Tag.choices, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    mentors = models.ManyToManyField(Mentor, related_name='events', blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            count = 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{count}"
                count += 1
            self.slug = slug
        super().save(*args, **kwargs)