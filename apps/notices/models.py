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
 
 
SLUG_MAX_LENGTH = 255


class Notice(TimeStampModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=SLUG_MAX_LENGTH, unique=True, blank=True, null=True, db_index=True)
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_title = self.title if self.pk else None

    def __str__(self):
        return self.title

    def _unique_slug(self, base_slug, start=1):
        """Return (slug, n) for the first free slug from base-n onward (base, base-2, ...), excluding this notice."""
        others = Notice.objects.exclude(pk=self.pk) if self.pk else Notice.objects.all()
        count = start
        while True:
            suffix = "" if count == 1 else f"-{count}"
            # Truncate the base so base + suffix always fits the column.
            candidate = f"{base_slug[:SLUG_MAX_LENGTH - len(suffix)].rstrip('-')}{suffix}"
            if not others.filter(slug=candidate).exists():
                return candidate, count
            count += 1

    def save(self, *args, **kwargs):
        title_changed = bool(self.pk is not None and self.title != self._original_title)
        # slugify produces ASCII slugs; titles with no Latin characters fall back to "notice".
        base_slug = slugify(self.title) or "notice"

        slug_number = None
        if not self.slug or title_changed:
            self.slug, slug_number = self._unique_slug(base_slug)

        from django.db import IntegrityError, transaction
        max_retries = 20
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                self._original_title = self.title
                break
            except IntegrityError as e:
                err_str = str(e).lower()
                if slug_number is not None and "slug" in err_str and attempt < max_retries - 1:
                    # A concurrent save took this slug between the check and the insert.
                    # Continue after the suffix that just failed so every retry makes progress.
                    self.slug, slug_number = self._unique_slug(base_slug, start=max(slug_number + 1, 2))
                else:
                    raise
