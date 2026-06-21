from .base import *
import os
import dj_database_url

# Production security rules
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DEBUG = False

# Restrict exclusively to production endpoints/IPs on the VPS
ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("ALLOWED_HOSTS", "cms.csitassociation.org").split(",") if host.strip()
]

# Production Database (PostgreSQL string passed via VPS Env)
DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=600,
        ssl_require=False  #true for cloud db
    )
}

# Production Asset Roots for Nginx tracking
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / "media"

# Secure Email configuration via Environment
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")

# Production Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True