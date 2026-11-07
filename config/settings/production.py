from .base import *
import os
import dj_database_url


USE_CLOUDINARY = os.environ.get("USE_CLOUDINARY", "true").lower() == "true"

if USE_CLOUDINARY:
    import cloudinary

    cloudinary.config(
        cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
        api_key=os.environ.get("CLOUDINARY_API_KEY"),
        api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
        secure=True,
    )

    INSTALLED_APPS += [
        'cloudinary',
        'cloudinary_storage',
    ]

    STORAGES = {
        **STORAGES,
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
    }


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY")
DEBUG = False
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "ALLOWED_HOSTS",
        "cms.csitabmc.com,cms-dashbaord-ben2.onrender.com"
    ).split(",")
    if host.strip()
]

_PROD_DEFAULT_ORIGINS = [
    "https://csitabmc-dashboard.vercel.app",
    "https://cms.csitabmc.com",
]

CORS_ALLOWED_ORIGINS = list(set(
    CORS_ALLOWED_ORIGINS + env_list("CORS_ALLOWED_ORIGINS", _PROD_DEFAULT_ORIGINS)
))

CSRF_TRUSTED_ORIGINS = list(set(
    CSRF_TRUSTED_ORIGINS + CORS_ALLOWED_ORIGINS + _PROD_DEFAULT_ORIGINS
))

# Auth cookies. Default SameSite=None preserves the current cross-site deployment
# (API on a different site than the dashboard). If the dashboard and API share a
# registrable domain (e.g. dashboard.example.com + api.example.com), set
# AUTH_COOKIE_SAMESITE=Lax. CSRF is enforced by Origin validation either way.
AUTH_COOKIE_SAMESITE = os.environ.get("AUTH_COOKIE_SAMESITE", "None")
AUTH_COOKIE_SECURE = True

# Only enable behind a proxy that overwrites X-Forwarded-Proto (Django docs prerequisite).
if env_bool("USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Without SMTP credentials, never fall back to the console backend in production:
# that would write password-reset links (secrets) into server logs.
if not EMAIL_CONFIGURED:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"


DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

# Static Files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# Email settings are read from the environment in base.py
# (EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL).


SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

X_FRAME_OPTIONS = "DENY"