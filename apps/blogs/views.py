import logging
import re
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import Http404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from apps.core.pagination import StandardPagination
from apps.core.permissions import HasModulePermission, HasPermission
from apps.core.activity_logging import diff_snapshots, log_activity, model_snapshot
from apps.core.media import MediaError, delete_asset
from apps.core.publishing import TRANSITION_VERBS, check_publish_permission, publish_transition
from .models import Blog, SecureFilePath
from .serializers import BlogSerializer, BlogListSerializer, BlogImageUploadSerializer

logger = logging.getLogger('blogs')

# Dashboard management API. Every method requires a permitted user so drafts are never
# exposed anonymously; future public endpoints should build on Blog.objects.published().

ALLOWED_ORDERING = {
    'id', '-id',
    'title', '-title',
    'created_at', '-created_at',
    'updated_at', '-updated_at',
    'published_at', '-published_at',
}
VALID_STATUSES = {choice for choice, _ in Blog.STATUS_CHOICES}
REFERENCE_SEARCH_RE = re.compile(rf'^{Blog.REFERENCE_PREFIX}-?(\d+)$', re.IGNORECASE)


class BlogListCreateView(APIView):
    permission_module = "blogs"
    parser_classes = (JSONParser,)
    permission_classes = [IsAuthenticated, HasModulePermission("blogs")]

    def get(self, request):
        queryset = Blog.objects.select_related('author')

        search = request.query_params.get('search') or request.query_params.get('title')
        status_filter = request.query_params.get('status')

        if search:
            search = search.strip()
            # Searching "ART-0042" (or "art42") finds the article by its display ID as well as by title
            reference = REFERENCE_SEARCH_RE.match(search)
            if reference:
                queryset = queryset.filter(Q(title__icontains=search) | Q(pk=int(reference.group(1))))
            else:
                queryset = queryset.filter(title__icontains=search)
        if status_filter:
            if status_filter not in VALID_STATUSES:
                return Response(
                    {"status": [f"Invalid status '{status_filter}'."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(status=status_filter)

        ordering = request.query_params.get('ordering', '-created_at')
        if ordering not in ALLOWED_ORDERING:
            ordering = '-created_at'
        queryset = queryset.order_by(ordering, '-id')

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = BlogListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        transition, denied = check_publish_permission(request, "blogs", None, request.data.get("status"))
        if denied:
            return denied
        serializer = BlogSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            blog = serializer.save()
            logger.info(f"Blog '{blog.title}' (Slug: {blog.slug}) created by user id {request.user.pk}")
            log_activity(request, action="create", module="blogs", target_id=blog.id, target_repr=blog.title,
                         description=f"Created blog '{blog.title}'")
            if transition == "publish":
                log_activity(request, action="publish", module="blogs", target_id=blog.id, target_repr=blog.title,
                             description=f"Published blog '{blog.title}'")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed to create blog. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BlogDetailView(APIView):
    permission_module = "blogs"
    parser_classes = (JSONParser,)
    permission_classes = [IsAuthenticated, HasModulePermission("blogs")]

    def get_object(self, pk):
        qs = Blog.objects.select_related('author')
        # Try slug first (covers numeric slugs)
        obj = qs.filter(slug=pk).first()
        if not obj and str(pk).isdigit():
            obj = qs.filter(pk=int(pk)).first()
        if not obj:
            raise Http404("Blog not found")
        return obj

    def get(self, request, pk):
        serializer = BlogSerializer(self.get_object(pk), context={'request': request})
        return Response(serializer.data)

    def _update(self, request, pk, partial):
        blog = self.get_object(pk)
        old_status = blog.status
        requested_status = request.data.get("status", old_status if partial else Blog.STATUS_DRAFT)
        _, denied = check_publish_permission(request, "blogs", old_status, requested_status)
        if denied:
            return denied
        before = model_snapshot(blog, exclude=("content",))
        serializer = BlogSerializer(blog, data=request.data, partial=partial, context={'request': request})
        if serializer.is_valid():
            updated_blog = serializer.save()
            action = publish_transition(old_status, updated_blog.status) or "update"
            changes = diff_snapshots(before, model_snapshot(updated_blog, exclude=("content",)))
            logger.info(f"Blog '{updated_blog.title}' updated ({action}) by user id {request.user.pk}")
            log_activity(request, action=action, module="blogs", target_id=updated_blog.id,
                         target_repr=updated_blog.title,
                         description=f"{TRANSITION_VERBS[None if action == 'update' else action]} blog '{updated_blog.title}'",
                         changes=changes)
            return Response(serializer.data)
        logger.warning(f"Failed to update blog {pk}. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def delete(self, request, pk):
        # blogs.delete is checked by HasModulePermission (see apps/core/permissions.py).
        blog = self.get_object(pk)
        title, blog_id = blog.title, blog.id
        blog.delete()
        logger.info(f"Blog '{title}' deleted by user id {request.user.pk}")
        log_activity(request, action="delete", module="blogs", target_id=blog_id, target_repr=title,
                     description=f"Deleted blog '{title}'")
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlogImageUploadThrottle(UserRateThrottle):
    scope = 'blog_image_upload'
    rate = '120/hour'


class BlogImageUploadView(APIView):
    """Uploads an article or featured image through the configured media storage (Cloudinary in production)."""
    permission_module = "blogs"
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, HasModulePermission("blogs")]
    throttle_classes = [BlogImageUploadThrottle]

    def post(self, request):
        serializer = BlogImageUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_file = serializer.validated_data['image']
        secure_filename = SecureFilePath('blogs/content/')(None, image_file.name)
        saved_path = default_storage.save(secure_filename, image_file)
        url = default_storage.url(saved_path)
        if not url.startswith(('http://', 'https://')):
            url = request.build_absolute_uri(url)

        logger.info(f"Blog image '{saved_path}' uploaded by user id {request.user.pk}")
        log_activity(request, action="media_upload", module="media", target_id=saved_path, target_repr=saved_path,
                     description="Uploaded blog image", details={"owner_module": "blogs"})
        return Response({"url": url, "public_id": saved_path}, status=status.HTTP_201_CREATED)



class BlogImageDeleteView(APIView):
    """
    Deletes an uploaded blog image from media storage, via the central media service:
    only blog-owned assets, only with media.delete + blogs.update, and only when no
    other record still references it. External URLs are never sent to storage.
    """
    permission_module = "blogs"
    permission_classes = [IsAuthenticated, HasModulePermission("blogs", "update"), HasPermission("media.delete")]

    def post(self, request):
        public_id = str(request.data.get('public_id') or '').strip()
        url = str(request.data.get('url') or '').strip()
        exclude_blog_id = request.data.get('exclude_blog_id')

        if not public_id and not url:
            return Response({"detail": "Either public_id or url is required to delete an asset."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not public_id:
            # An external URL is only a reference; removing it from the article is enough.
            return Response({"detail": "External image reference removed; no stored media was deleted."},
                            status=status.HTTP_200_OK)

        try:
            delete_asset(request.user, public_id, exclude_blog_id=exclude_blog_id, required_module="blogs", url=url)
        except MediaError as exc:
            body = {"detail": exc.message}
            if exc.references:
                body["references"] = [f"{r['module'].capitalize()}: {r['label']}" for r in exc.references]
            return Response(body, status=exc.status_code)

        logger.info(f"Media asset '{public_id}' deleted by user id {request.user.pk}")
        log_activity(request, action="media_delete", module="media", target_id=public_id, target_repr=public_id,
                     description="Deleted unused blog image", details={"owner_module": "blogs"})
        return Response({"detail": "Asset permanently destroyed from media storage."}, status=status.HTTP_200_OK)