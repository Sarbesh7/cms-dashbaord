from urllib.parse import urlparse

from django.conf import settings
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from .tokens import ACCESS_COOKIE, token_matches_user

SAFE_METHODS = ("GET", "HEAD", "OPTIONS", "TRACE")


def _request_origin(request):
    origin = request.META.get("HTTP_ORIGIN")
    if origin:
        return origin.rstrip("/")
    referer = request.META.get("HTTP_REFERER")
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return None


def trusted_origins():
    return {o.rstrip("/") for o in (*settings.CORS_ALLOWED_ORIGINS, *settings.CSRF_TRUSTED_ORIGINS)}


def enforce_trusted_origin(request):
    """
    CSRF defense for cookie-authenticated, state-changing requests (S2).

    Browsers attach the auth cookie to cross-site requests, but they always send
    an Origin header (or at least a Referer) that a page cannot forge. Unsafe
    requests are accepted only from the API's own origin or a configured trusted
    origin (CORS_ALLOWED_ORIGINS / CSRF_TRUSTED_ORIGINS).
    """
    if request.method.upper() in SAFE_METHODS:
        return
    origin = _request_origin(request)
    if not origin:
        raise exceptions.PermissionDenied("CSRF Failed: Origin header is missing.")
    own_origin = f"{request.scheme}://{request.get_host()}"
    if origin != own_origin and origin not in trusted_origins():
        raise exceptions.PermissionDenied("CSRF Failed: Origin is not trusted.")


class CookieJWTAuthentication(JWTAuthentication):
    """
    JWT from the Authorization header (non-browser clients) or the httpOnly
    access_token cookie (dashboard). Cookie-authenticated unsafe requests must
    come from a trusted Origin. All tokens must match the user's current
    password (see apps/users/tokens.py).
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not token_matches_user(validated_token, user):
            raise InvalidToken("Token is no longer valid. Please log in again.")
        return user

    def authenticate(self, request):
        # A bearer header cannot be attached by a cross-site page, so it needs no CSRF check.
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(ACCESS_COOKIE)
        if not raw_token:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
        except (InvalidToken, exceptions.AuthenticationFailed):
            # Expired/revoked cookie: treat as anonymous so the client can refresh or re-login.
            return None

        enforce_trusted_origin(request)
        return user, validated_token
