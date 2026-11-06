from .base import *
import os
import dj_database_url
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-key-change-me")
DEBUG = True

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if host.strip()
]

import sys

if 'test' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
    class DisableMigrations:
        def __contains__(self, item):
            return True
        def __getitem__(self, item):
            return None
    MIGRATION_MODULES = DisableMigrations()
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    DATABASES = {
        'default': dj_database_url.config(
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
            conn_max_age=600
        )
    }

# Local file routing
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

USE_CLOUDINARY = (os.getenv("USE_CLOUDINARY", "False").lower() == "true") and ('test' not in sys.argv)

if USE_CLOUDINARY:
    import cloudinary

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
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

# Email: configured in base.py from environment variables (SMTP only when
# EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are set, otherwise the console backend).

# Local dashboard default for password-reset links (production must set FRONTEND_URL).
FRONTEND_URL = FRONTEND_URL or "http://localhost:3000"

# Local development runs over plain HTTP on the same site as the dashboard.
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "Lax")
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", False)

if 'test' in sys.argv:
    # Generous limits so the suite is not throttled; throttling tests override explicitly.
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
        scope: '10000/minute' for scope in REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
    }
    DUPLICATE_REQUEST_WINDOW = 0
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    EMAIL_CONFIGURED = True
    FRONTEND_URL = "http://localhost:3000"