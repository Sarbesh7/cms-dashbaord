import hashlib

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

# Auth endpoints have their own throttles and idempotent semantics.
EXEMPT_PREFIXES = (
    "/api/v1/login/",
    "/api/v1/users/refresh-token/",
    "/api/v1/users/logout/",
)
MAX_HASHED_BODY = 1024 * 1024  # larger/multipart bodies are not buffered (uploads are throttled instead)


class DuplicateRequestMiddleware:
    """
    Reject an identical authenticated POST repeated within DUPLICATE_REQUEST_WINDOW
    seconds (double clicks, client retries). The key is the caller's credential,
    path and exact body, so different submissions are never blocked. A failed
    first attempt releases the key so the user can retry immediately.
    Uses the configured Django cache; no extra infrastructure.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        window = int(getattr(settings, "DUPLICATE_REQUEST_WINDOW", 0) or 0)
        if (
            window <= 0
            or request.method != "POST"
            or not request.path.startswith("/api/")
            or request.path.startswith(EXEMPT_PREFIXES)
            or request.content_type == "multipart/form-data"
        ):
            return self.get_response(request)

        identity = request.COOKIES.get("access_token") or request.META.get("HTTP_AUTHORIZATION")
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if not identity or length > MAX_HASHED_BODY:
            return self.get_response(request)

        digest = hashlib.sha256()
        for part in (identity.encode(), request.path.encode(), request.body):
            digest.update(part)
            digest.update(b"\x00")
        key = f"dup-request:{digest.hexdigest()}"

        if not cache.add(key, 1, window):
            return JsonResponse(
                {"detail": "This request was already submitted. Please wait a moment before retrying."},
                status=409,
            )
        response = self.get_response(request)
        if response.status_code >= 400:
            cache.delete(key)
        return response
