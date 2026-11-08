import os
import re
import uuid
from django.db import models, transaction, IntegrityError
from django.utils import timezone
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from apps.core.models import TimeStampModel

MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_file_size(value):
    # Referenced by migration 0001
    if value.size > MAX_IMAGE_UPLOAD_SIZE:
        raise ValidationError('File too large. Size should not exceed 5 MB.')


@deconstructible
class SecureFilePath:
    def __init__(self, folder_name):
        self.folder_name = folder_name

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()
        secure_name = f"{uuid.uuid4()}{ext}"
        return os.path.join(self.folder_name, secure_name)


SLUG_MAX_LENGTH = 300
EXCERPT_MAX_LENGTH = 300
SEO_DESCRIPTION_MAX_LENGTH = 160


def markdown_to_plain_text(text):
    """Rough Markdown -> plain text conversion used for SEO description fallbacks."""
    if not text:
        return ''
    text = re.sub(r'```.*?```', ' ', text, flags=re.DOTALL)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)            # images
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)          # links -> label
    text = re.sub(r'<[^>]+>', ' ', text)                          # inline html
    text = re.sub(r'^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'[*_`~]+', '', text)
    text = re.sub(r'^\s*-{3,}\s*$', ' ', text, flags=re.MULTILINE)
    return re.sub(r'\s+', ' ', text).strip()


def truncate_words(text, limit):
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(' ', 1)[0]
    return f"{cut.rstrip(',.;:')}…"


class BlogQuerySet(models.QuerySet):
    def published(self):
        """Only blogs that are safe to expose on future public endpoints."""
        return self.filter(status=Blog.STATUS_PUBLISHED, published_at__isnull=False)


class Blog(TimeStampModel):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PUBLISHED, 'Published'),
    ]

    title = models.CharField(max_length=255)
    # Generated from the title on the backend; never edited directly
    slug = models.SlugField(max_length=SLUG_MAX_LENGTH, unique=True, blank=True, db_index=True, editable=False)
    excerpt = models.TextField(max_length=EXCERPT_MAX_LENGTH, blank=True, default='')
    # Markdown article body. Images are referenced by URL only.
    content = models.TextField()
    # Editor-uploaded images: [{"url": ..., "public_id": ..., "alt": ...}]
    content_images = models.JSONField(default=list, blank=True)

    # Featured image: external URL or an uploaded asset (Cloudinary in production)
    featured_image_url = models.URLField(max_length=1000, null=True, blank=True)
    featured_image_public_id = models.CharField(max_length=255, blank=True, default='')
    featured_image_alt = models.CharField(max_length=255, blank=True, default='')

    # Organization Member credited for the article (any tenure). Independent of the
    # dashboard account that edits the record. Required to publish, optional for drafts.
    # SET_NULL keeps articles when a member is deleted; they then need a new author to be re-published.
    author = models.ForeignKey(
        'tenure.Member',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blogs',
    )
    # Credited name kept for historical articles if the Member is deleted.
    author_name_snapshot = models.CharField(max_length=100, blank=True, default='')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)

    objects = BlogQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Blog'
        verbose_name_plural = 'Blogs'
        indexes = [
            models.Index(fields=['status', '-created_at', '-id'], name='blog_status_created_idx'),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_title = self.title if self.pk else None

    def __str__(self):
        return self.title

    REFERENCE_PREFIX = 'ART'

    @property
    def reference(self):
        """Human-friendly article ID shown in the dashboard, e.g. ART-0042 (derived from the primary key)."""
        return f"{self.REFERENCE_PREFIX}-{self.pk:04d}" if self.pk else None

    def _unique_slug(self, base_slug, start=1):
        """Return (slug, n) for the first available slug from base-n onward, excluding this blog."""
        others = Blog.objects.exclude(pk=self.pk) if self.pk else Blog.objects.all()
        count = start
        while True:
            suffix = "" if count == 1 else f"-{count}"
            candidate = f"{base_slug[:SLUG_MAX_LENGTH - len(suffix)].rstrip('-')}{suffix}"
            if not others.filter(slug=candidate).exists():
                return candidate, count
            count += 1

    # --- Automatically derived SEO values -----------------------------
    # No manual SEO fields: everything comes from title, excerpt, content and featured image.

    @property
    def seo_title(self):
        return self.title

    @property
    def seo_description(self):
        if self.excerpt and self.excerpt.strip():
            return truncate_words(re.sub(r'\s+', ' ', self.excerpt).strip(), SEO_DESCRIPTION_MAX_LENGTH)
        return truncate_words(markdown_to_plain_text(self.content), SEO_DESCRIPTION_MAX_LENGTH)

    @property
    def og_title(self):
        return self.seo_title

    @property
    def og_description(self):
        return self.seo_description

    @property
    def og_image_url(self):
        return self.featured_image_url or None

    # --- Persistence ---------------------------------------------------

    def save(self, *args, **kwargs):
        # Slugs are always derived from the title (same convention as Notices):
        # generated on create and regenerated whenever the title changes.
        title_changed = bool(self.pk is not None and self.title != self._original_title)
        base_slug = slugify(self.title) or "blog"

        slug_number = None
        if not self.slug or title_changed:
            self.slug, slug_number = self._unique_slug(base_slug)

        if self.author_id:
            self.author_name_snapshot = self.author.name

        if self.status == self.STATUS_PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        # Concurrency-safe save: another writer may claim the slug between check and insert
        max_retries = 20
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                self._original_title = self.title
                break
            except IntegrityError as e:
                if slug_number is not None and "slug" in str(e).lower() and attempt < max_retries - 1:
                    self.slug, slug_number = self._unique_slug(base_slug, start=max(slug_number + 1, 2))
                else:
                    raise
