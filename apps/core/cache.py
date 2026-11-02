from functools import wraps

from django.core.cache import cache
from django.views.decorators.cache import cache_page
from rest_framework.response import Response

CONTENT_CACHE_VERSION_KEY = "content-cache-version"


def get_content_cache_version():
    return cache.get_or_set(CONTENT_CACHE_VERSION_KEY, 1, None)


def bump_content_cache_version(*args, **kwargs):
    """Invalidate every versioned_cache_page response. Usable directly as a signal receiver."""
    try:
        cache.incr(CONTENT_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(CONTENT_CACHE_VERSION_KEY, 2, None)


def versioned_cache_page(timeout):
    """cache_page for APIView methods whose key changes whenever content is written."""
    def decorator(view_method):
        @wraps(view_method)
        def _wrapped(self, request, *args, **kwargs):
            # The cache key is URL-only, so only the public (anonymous) variant may be
            # cached. Authenticated responses can include drafts and private fields.
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                response = view_method(self, request, *args, **kwargs)
                response["Cache-Control"] = "private, no-store"
                return response
            key_prefix = f"content-v{get_content_cache_version()}"
            cached_view = cache_page(timeout, key_prefix=key_prefix)(
                lambda req, *a, **kw: view_method(self, req, *a, **kw)
            )
            return cached_view(request, *args, **kwargs)
        return _wrapped
    return decorator


class StandardCacheMixin:

    cache_timeout = 60 * 15  # Default: 15 minutes
    cache_prefix = None      # Unique string set per ViewSet (e.g., "notices")

    def get_cache_prefix(self):
       
        return self.cache_prefix or self.__class__.__name__.lower()

    def get_cache_key(self):
       
        prefix = self.get_cache_prefix()
        full_path = self.request.get_full_path()
        return f"{prefix}:{full_path}"

    def clear_cache(self):
      
        cache.clear()

    def list(self, request, *args, **kwargs):
        cache_key = self.get_cache_key()
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        
        # Caches raw response data dictionary (safe for paginated structures)
        cache.set(cache_key, response.data, self.cache_timeout)
        return response

    def retrieve(self, request, *args, **kwargs):
        cache_key = self.get_cache_key()
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, self.cache_timeout)
        return response

   #invalid cache
    def perform_create(self, serializer):
        super().perform_create(serializer)
        self.clear_cache()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self.clear_cache()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self.clear_cache()

class StandardCachePaginationMixin(StandardCacheMixin):
    def list(self, request, *args, **kwargs):
        cache_key = self.get_cache_key()
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        
        # Caches raw response data dictionary (safe for paginated structures)
        cache.set(cache_key, response.data, self.cache_timeout)
        return response
    
class StandardCacheRetrieveMixin(StandardCacheMixin):
    def retrieve(self, request, *args, **kwargs):
        cache_key = self.get_cache_key()
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, self.cache_timeout)
        return response