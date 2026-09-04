from django.core.cache import cache
from rest_framework.response import Response

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