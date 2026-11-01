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
from apps.core.permission import IsAdmin, IsCMSUser
from .models import Blog, SecureFilePath
from .serializers import BlogSerializer, BlogListSerializer, BlogImageUploadSerializer

logger = logging.getLogger('blogs')

# Dashboard management API. Every method requires a CMS user so drafts are never
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
    parser_classes = (JSONParser,)
    permission_classes = [IsAuthenticated, IsCMSUser]

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
        serializer = BlogSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            blog = serializer.save()
            logger.info(f"Blog '{blog.title}' (Slug: {blog.slug}) created by User: {request.user}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed to create blog. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BlogDetailView(APIView):
    parser_classes = (JSONParser,)
    permission_classes = [IsAuthenticated, IsCMSUser]

    def get_object(self, pk):
        try:
            return Blog.objects.select_related('author').get(pk=pk)
        except Blog.DoesNotExist:
            raise Http404("Blog not found")

    def get(self, request, pk):
        serializer = BlogSerializer(self.get_object(pk), context={'request': request})
        return Response(serializer.data)

    def _update(self, request, pk, partial):
        blog = self.get_object(pk)
        serializer = BlogSerializer(blog, data=request.data, partial=partial, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Blog '{blog.title}' updated by User: {request.user}")
            return Response(serializer.data)
        logger.warning(f"Failed to update blog {pk}. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def delete(self, request, pk):
        # Admin or superuser required for deletion
        if not IsAdmin().has_permission(request, self) and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to delete this blog."},
                status=status.HTTP_403_FORBIDDEN
            )

        blog = self.get_object(pk)
        title = blog.title
        blog.delete()
        logger.info(f"Blog '{title}' deleted by User: {request.user}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlogImageUploadThrottle(UserRateThrottle):
    scope = 'blog_image_upload'
    rate = '120/hour'


class BlogImageUploadView(APIView):
    """Uploads an article or featured image through the configured media storage (Cloudinary in production)."""
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, IsCMSUser]
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

        logger.info(f"Blog image '{saved_path}' uploaded by User: {request.user}")
        return Response({"url": url, "public_id": saved_path}, status=status.HTTP_201_CREATED)
