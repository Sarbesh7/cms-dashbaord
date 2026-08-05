import os
import uuid
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from apps.core.models import TimeStampModel


def validate_file_size(value):
    limit = 5 * 1024 * 1024  # 5 MB Limit
    if value.size > limit:
        raise ValidationError("File too large. Size should not exceed 5 MB.")


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
    slug = models.SlugField(unique=True, db_index=True)

    class Meta:
        ordering = ["-start_date"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Member(TimeStampModel):

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    image = models.ImageField(
        upload_to=SecureFilePath("member_images/"),
        validators=[validate_file_size],
        null=True,
        blank=True,
    )

    fb_link = models.URLField(null=True, blank=True)
    linkedin_link = models.URLField(null=True, blank=True)
    github_link = models.URLField(null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True, db_index=True)

    class Meta:
        ordering = ["name"]

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
        EXECUTIVE = "EXECUTIVE", "Executive Board"
        ADVISOR = "ADVISOR", "Advisor"

    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="memberships"
    )
    tenure = models.ForeignKey(
        Tenure, on_delete=models.CASCADE, related_name="memberships"
    )
    role_type = models.CharField(
        max_length=20, choices=RoleType.choices, default=RoleType.EXECUTIVE
    )
    designation = models.CharField(
        max_length=100, help_text="e.g. President, Vice President, Treasurer"
    )

    order = models.PositiveIntegerField(
        default=99,
        help_text="Order of hierarchy: 1=President, 2=Vice President, 3=Secretary, etc.",
    )

    class Meta:
        unique_together = ("member", "tenure")

        ordering = ["order", "id"]

    def __str__(self):
        return f"[{self.order}] {self.member.name} - {self.designation} ({self.tenure.name})"


class Alumni(TimeStampModel):
    member = models.OneToOneField(
        Member, on_delete=models.CASCADE, related_name="alumni_profile"
    )
    tenures = models.ManyToManyField(Tenure, related_name="alumni")
    graduation_year = models.IntegerField(null=True, blank=True)
    bio = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Alumni: {self.member.name}"
