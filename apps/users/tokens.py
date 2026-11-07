"""
JWT issuance, cookie handling and credential invalidation.

Immediate invalidation after a password change (S3)
---------------------------------------------------
Every token carries an ``auth_hash`` claim: a keyed HMAC (SECRET_KEY) of the
user's current password hash, the same idea Django uses for session auth.
Changing or resetting a password changes ``user.password``, so every token
issued before the change stops matching on its next use, both access tokens
(checked on each request) and refresh tokens (checked on refresh).

Cost: zero extra queries. simplejwt already loads the user row per request; the
check is one HMAC. Outstanding refresh tokens are also blacklisted on password
change as defense in depth (one bulk insert).
"""
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

AUTH_HASH_CLAIM = "auth_hash"
SESSION_START_CLAIM = "session_start"
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def compute_auth_hash(user):
    return salted_hmac("apps.users.tokens.auth_hash", user.password or "", algorithm="sha256").hexdigest()[:32]


def token_matches_user(token, user):
    claim = token.get(AUTH_HASH_CLAIM) if hasattr(token, "get") else None
    return bool(claim) and constant_time_compare(str(claim), compute_auth_hash(user))


def cookie_kwargs(max_age):
    return {
        "httponly": True,
        "secure": getattr(settings, "AUTH_COOKIE_SECURE", not settings.DEBUG),
        "samesite": getattr(settings, "AUTH_COOKIE_SAMESITE", "Lax"),
        "domain": getattr(settings, "AUTH_COOKIE_DOMAIN", None),
        "path": getattr(settings, "AUTH_COOKIE_PATH", "/"),
        "max_age": max_age,
    }


def issue_tokens(user, session_start=None):
    """Refresh + access token pair bound to the user's current password."""
    refresh = RefreshToken.for_user(user)
    refresh[SESSION_START_CLAIM] = int(session_start or timezone.now().timestamp())
    refresh[AUTH_HASH_CLAIM] = compute_auth_hash(user)
    return refresh, refresh.access_token


def apply_partitioned_cookie(response, names):
    """
    Apply the 'Partitioned' attribute (CHIPS) when cookies are SameSite=None and Secure.
    Allows cross-site HttpOnly cookies to function in Incognito mode and modern browsers
    with third-party cookie restrictions (Chrome, Edge, Firefox).
    """
    kwargs = cookie_kwargs(0)
    if str(kwargs.get("samesite") or "").lower() == "none" and kwargs.get("secure"):
        for name in names:
            if name in response.cookies:
                try:
                    response.cookies[name]["partitioned"] = True
                except Exception:
                    pass


def set_session_cookies(response, refresh, access):
    response.set_cookie(ACCESS_COOKIE, str(access),
                        **cookie_kwargs(int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds())))
    response.set_cookie(REFRESH_COOKIE, str(refresh),
                        **cookie_kwargs(int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds())))
    apply_partitioned_cookie(response, (ACCESS_COOKIE, REFRESH_COOKIE))
    return response


def clear_session_cookies(response):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.set_cookie(name, "", **cookie_kwargs(0))
    apply_partitioned_cookie(response, (ACCESS_COOKIE, REFRESH_COOKIE))
    return response


def revoke_user_refresh_tokens(user):
    """Blacklist every outstanding refresh token of one user (bulk, idempotent)."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    pending = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create([BlacklistedToken(token=t) for t in pending], ignore_conflicts=True)
