import os
import uuid
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django.db.models.signals import pre_delete
from django.dispatch import receiver
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
    signature= models.ImageField(
        upload_to=SecureFilePath("president_signatures/"),
        validators=[validate_file_size],
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-start_date"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            counter = 1
            while Tenure.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Member(TimeStampModel):

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    image = models.ImageField(
        upload_to=SecureFilePath("member_images/"),
        validators=[validate_file_size],
        null=True,
        blank=True,
    )

    fb_link = models.URLField(null=True, blank=True)
    linkedin_link = models.URLField(null=True, blank=True)
    github_link = models.URLField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    skills = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("published", "Published"), ("draft", "Draft")],
        default="published",
    )
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
        

    # SET_NULL keeps the historical committee record when a Member is deleted;
    # member_name_snapshot keeps it displayable.
    member = models.ForeignKey(
        Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships"
    )
    member_name_snapshot = models.CharField(max_length=100, blank=True, default="")
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
    status = models.CharField(
        max_length=20,
        choices=[("published", "Published"), ("draft", "Draft")],
        default="published",
    )

    class Meta:
        unique_together = ("member", "tenure")
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["status", "order"]),
        ]

    @property
    def member_name(self):
        return self.member.name if self.member_id else self.member_name_snapshot

    def save(self, *args, **kwargs):
        if self.member_id:
            self.member_name_snapshot = self.member.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.order}] {self.member_name} - {self.designation} ({self.tenure.name})"


class Alumni(TimeStampModel):
    # SET_NULL keeps alumni history when the Member record is deleted.
    member = models.OneToOneField(
        Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="alumni_profile"
    )
    member_name_snapshot = models.CharField(max_length=100, blank=True, default="")
    tenures = models.ManyToManyField(Tenure, related_name="alumni")
    graduation_year = models.IntegerField(null=True, blank=True)
    bio = models.TextField(null=True, blank=True)

    @property
    def member_name(self):
        return self.member.name if self.member_id else self.member_name_snapshot

    def save(self, *args, **kwargs):
        if self.member_id:
            self.member_name_snapshot = self.member.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Alumni: {self.member_name}"


def snapshot_member_references(member):
    """Copy the member's name onto every historical record before the FK is nulled."""
    TenureMembership.objects.filter(member=member).update(member_name_snapshot=member.name)
    Alumni.objects.filter(member=member).update(member_name_snapshot=member.name)
    from apps.blogs.models import Blog
    Blog.objects.filter(author=member).update(author_name_snapshot=member.name)


@receiver(pre_delete, sender=Member, dispatch_uid="tenure-member-snapshot-before-delete")
def _snapshot_before_member_delete(sender, instance, **kwargs):
    # Runs for single and bulk (queryset/admin) deletes alike.
    snapshot_member_references(instance)
