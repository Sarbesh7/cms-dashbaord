import os
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from apps.tenure.models import Member
from .models import Blog, MAX_IMAGE_UPLOAD_SIZE
from .validators import validate_markdown_content, validate_http_url


def _as_drf_error(exc):
    return serializers.ValidationError(exc.messages)


class ContentImageSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=1000)
    public_id = serializers.CharField(max_length=255, allow_blank=True, required=False, default='')
    alt = serializers.CharField(max_length=255, allow_blank=True, required=False, default='')

    def validate_url(self, value):
        try:
            return validate_http_url(value)
        except DjangoValidationError as exc:
            raise _as_drf_error(exc)


class BlogAuthorSerializer(serializers.ModelSerializer):
    """Read-only view of the credited Organization Member; profile data stays on the Member record."""
    image = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = ['id', 'name', 'slug', 'image']

    def get_image(self, obj):
        if not obj.image:
            return None
        url = obj.image.url
        request = self.context.get('request')
        if request and not url.startswith(('http://', 'https://')):
            return request.build_absolute_uri(url)
        return url


class BlogSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    author = BlogAuthorSerializer(read_only=True)
    # Any Organization Member can be credited, regardless of tenure
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=Member.objects.all(),
        source='author',
        allow_null=True,
        required=False,
        write_only=True,
        error_messages={'does_not_exist': 'Selected author does not exist.'},
    )
    content_images = ContentImageSerializer(many=True, required=False)
    seo = serializers.SerializerMethodField()
    # Credited name, kept even if the Member record is later deleted.
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        fields = [
            'id',
            'reference',
            'title',
            'slug',
            'author',
            'author_id',
            'author_name',
            'excerpt',
            'content',
            'content_images',
            'featured_image_url',
            'featured_image_public_id',
            'featured_image_alt',
            'status',
            'published_at',
            'created_at',
            'updated_at',
            'seo',
        ]
        # Slug is generated from the title on the backend and cannot be set by clients
        read_only_fields = [
            'id',
            'slug',
            'published_at',
            'created_at',
            'updated_at',
            'seo',
        ]

    def get_author_name(self, obj):
        return obj.author.name if obj.author_id else (obj.author_name_snapshot or None)

    def get_seo(self, obj):
        # Derived automatically; the public frontend builds the canonical URL from its own domain + path
        return {
            'title': obj.seo_title,
            'description': obj.seo_description,
            'og_title': obj.og_title,
            'og_description': obj.og_description,
            'og_image': obj.og_image_url,
            'og_image_alt': obj.featured_image_alt or obj.title,
            'author': obj.author.name if obj.author else None,
            'slug': obj.slug,
            'path': f'/blogs/{obj.slug}',
        }

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Blog title is required.")
        return value

    def validate_content(self, value):
        try:
            return validate_markdown_content(value)
        except DjangoValidationError as exc:
            raise _as_drf_error(exc)

    def validate_featured_image_url(self, value):
        if not value:
            return None
        try:
            return validate_http_url(value, 'Featured image URL')
        except DjangoValidationError as exc:
            raise _as_drf_error(exc)

    def validate(self, attrs):
        content = attrs.get('content', getattr(self.instance, 'content', ''))

        # Keep only references to editor-uploaded images still present in the content
        if 'content_images' in attrs or 'content' in attrs:
            images = attrs.get('content_images')
            if images is None:
                images = getattr(self.instance, 'content_images', None) or []
            seen = set()
            kept = []
            for image in images:
                url = image.get('url')
                if url and url in content and url not in seen:
                    seen.add(url)
                    kept.append({
                        'url': url,
                        'public_id': image.get('public_id', ''),
                        'alt': image.get('alt', ''),
                    })
            attrs['content_images'] = kept

        # Removing the featured image clears its asset reference and alt text
        if 'featured_image_url' in attrs and not attrs['featured_image_url']:
            attrs['featured_image_public_id'] = ''
            attrs['featured_image_alt'] = ''

        # Drafts may be saved without an author; publishing requires one
        status = attrs.get('status', getattr(self.instance, 'status', Blog.STATUS_DRAFT))
        author = attrs['author'] if 'author' in attrs else getattr(self.instance, 'author', None)
        if status == Blog.STATUS_PUBLISHED and author is None:
            raise serializers.ValidationError(
                {'author_id': ['Select an author before publishing this article.']}
            )
        return attrs


class BlogListSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    author = BlogAuthorSerializer(read_only=True)
    author_name = serializers.SerializerMethodField()

    def get_author_name(self, obj):
        return obj.author.name if obj.author_id else (obj.author_name_snapshot or None)

    class Meta:
        model = Blog
        fields = [
            'id',
            'reference',
            'title',
            'author',
            'author_name',
            'slug',
            'excerpt',
            'status',
            'featured_image_url',
            'featured_image_alt',
            'published_at',
            'created_at',
            'updated_at',
        ]


IMAGE_EXTENSION_TYPES = {
    'jpg': {'image/jpeg'},
    'jpeg': {'image/jpeg'},
    'png': {'image/png'},
    'webp': {'image/webp'},
    'gif': {'image/gif'},
}


class BlogImageUploadSerializer(serializers.Serializer):
    # ImageField verifies the payload is a real image via Pillow
    image = serializers.ImageField(required=True)

    def validate_image(self, value):
        if value.size > MAX_IMAGE_UPLOAD_SIZE:
            raise serializers.ValidationError("Image size cannot exceed 5MB.")

        ext = os.path.splitext(value.name)[1].lower().lstrip('.')
        if ext not in IMAGE_EXTENSION_TYPES:
            raise serializers.ValidationError(
                f"Unsupported file extension .{ext}. Supported types: {', '.join(IMAGE_EXTENSION_TYPES)}"
            )

        detected = getattr(getattr(value, 'image', None), 'format', None)
        detected_mime = f"image/{detected.lower()}" if detected else None
        if detected_mime and detected_mime not in IMAGE_EXTENSION_TYPES[ext]:
            raise serializers.ValidationError("File extension does not match the image content.")
        return value
