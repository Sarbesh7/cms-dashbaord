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
 

class Tenure(TimeStampModel):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    slug = models.SlugField(unique=True, db_index=True  )

    def __str__(self):
        return self.name


class Member(TimeStampModel):
    # tenure = models.ForeignKey(Tenure, on_delete=models.CASCADE, related_name="members")
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    
   
    image = models.ImageField(
        upload_to=SecureFilePath('member_images/'),
        validators=[validate_file_size],
        null=True, 
        blank=True
    )
    
    
    fb_link = models.URLField(null=True, blank=True)
    linkedin_link = models.URLField(null=True, blank=True)
    github_link = models.URLField(null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True, db_index=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Member.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = slugify(f"{self.name}-{counter}")
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class TenureMembership(TimeStampModel):
    class RoleType(models.TextChoices):
        MEMBER = 'MEMBER', 'Member'
        ADVISOR = 'ADVISOR', 'Advisor'

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="memberships")
    tenure = models.ForeignKey(Tenure, on_delete=models.CASCADE, related_name="memberships")
    role_type = models.CharField(max_length=20, choices=RoleType.choices, default=RoleType.MEMBER)
    designation = models.CharField(max_length=100, help_text="e.g. Senior Advisor")

    class Meta:
        unique_together = ('member', 'tenure', 'role_type')

    def __str__(self):
        return f"{self.member.name} - {self.get_role_type_display()} ({self.tenure.name})"




class Alumni(TimeStampModel):  
    member = models.OneToOneField(
        Member, 
        on_delete=models.CASCADE, 
        related_name="alumni_profile"
    )
    tenures = models.ManyToManyField(Tenure, related_name="alumni")  
    graduation_year = models.IntegerField(null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    def __str__(self):
        return f"Alumni: {self.member.name}"