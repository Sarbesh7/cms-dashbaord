from pathlib import Path
from datetime import timedelta
import os

# Corrected path calculation for being 3 folders deep now
BASE_DIR = Path(__file__).resolve().parent.parent.parent

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": MEDIA_ROOT,
            "base_url": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
    
INSTALLED_APPS = [         
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'apps.users',
    'apps.events',
    'apps.notices',
    'apps.certificates',
    'apps.tenure',
    'apps.core',
    'apps.papers',
    'apps.blogs',
    'apps.notifications',
    'apps.announcements',
    'rest_framework.authtoken',

    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.DuplicateRequestMiddleware',
]

ROOT_URLCONF = 'config.urls'


def env_list(name, default=None):
    """Comma-separated environment variable -> list (empty entries dropped)."""
    raw = os.environ.get(name)
    if raw is None:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


_LOCAL_DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

# Browser origins (scheme://host[:port]) allowed to call the API with credentials.
# Set CORS_ALLOWED_ORIGINS to the dashboard (and public website, if it calls the API).
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", _LOCAL_DEV_ORIGINS)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", CORS_ALLOWED_ORIGINS)
CORS_ALLOW_CREDENTIALS = True

# Authentication cookie attributes (see apps/users/cookies.py).
# SameSite defaults are chosen per settings module; override with AUTH_COOKIE_SAMESITE.
AUTH_COOKIE_DOMAIN = os.environ.get("AUTH_COOKIE_DOMAIN") or None
AUTH_COOKIE_PATH = "/"
AUTH_COOKIE_SAMESITE = os.environ.get("AUTH_COOKIE_SAMESITE", "Lax")
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", True)

# Client-IP resolution for activity logs (apps/core/activity_logging.get_client_ip).
# Forwarded headers are trusted ONLY when REMOTE_ADDR is in TRUSTED_PROXIES (IPs/CIDRs).
TRUSTED_PROXIES = env_list("TRUSTED_PROXIES", [])
CLIENT_IP_HEADER = os.environ.get("CLIENT_IP_HEADER", "")  # e.g. "CF-Connecting-IP"

# Frontend URL
FRONTEND_URL = (os.environ.get("FRONTEND_URL") or "").rstrip("/")

# Email: credentials come only from the environment; nothing is hardcoded.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "webmaster@localhost"
EMAIL_TIMEOUT = 15
EMAIL_CONFIGURED = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_CONFIGURED
    else "django.core.mail.backends.console.EmailBackend"
)

# Seconds within which an identical authenticated POST is rejected as a duplicate (0 disables).
DUPLICATE_REQUEST_WINDOW = int(os.environ.get("DUPLICATE_REQUEST_WINDOW", 3))


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.users.authentication.CookieJWTAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '120/minute',
        'login': '5/minute',
        'login_account': '10/hour',
        'password_reset': '3/minute',
        'password_reset_account': '3/hour',
        'certificate_verify': '30/minute',
        'account_management': '60/minute',
        'media': '60/hour',
        'blog_image_upload': '120/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
}

AUTH_USER_MODEL = "users.User"

# Session policy: 1-hour access tokens; 7-day refresh tokens rotated (and the old
# one blacklisted) on every refresh, so each refresh opens a new 7-day window
# (sliding expiration). JWT_SESSION_MAX_LIFETIME caps a session absolutely,
# counted from the original login, regardless of activity.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
JWT_SESSION_MAX_LIFETIME = timedelta(days=30)

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'apps.users.password_validation.PasswordComplexityValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

IS_RENDER = os.environ.get("RENDER") == "true"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {},
    "loggers": {},
}

if IS_RENDER:
    # Console logging for Render
    LOGGING["handlers"] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    }

    LOGGING["loggers"] = {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "security": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "certificate": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "paper": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "event": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "notice": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "tenure": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    }

else:
    # Local file logging
    LOG_DIR = BASE_DIR / "logs"
    os.makedirs(LOG_DIR, exist_ok=True)

    LOGGING["handlers"] = {
        "django_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "django.log",
            "formatter": "standard",
        },
        "error_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "errors.log",
            "formatter": "standard",
            "level": "ERROR",
        },
        "security_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "security.log",
            "formatter": "standard",
        },
        "certificate_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "certificate.log",
            "formatter": "standard",
        },
        "paper_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "pastpaper.log",
            "formatter": "standard",
        },
        "event_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "event.log",
            "formatter": "standard",
        },
        "notice_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "notice.log",
            "formatter": "standard",
        },
        "tenure_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "tenure.log",
            "formatter": "standard",
        },
    }

    LOGGING["loggers"] = {
        "django": {
            "handlers": ["django_file", "error_file"],
            "level": "INFO",
            "propagate": True,
        },
        "security": {
            "handlers": ["security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "certificate": {
            "handlers": ["certificate_file"],
            "level": "INFO",
            "propagate": False,
        },
        "paper": {
            "handlers": ["paper_file"],
            "level": "INFO",
            "propagate": False,
        },
        "event": {
            "handlers": ["event_file"],
            "level": "INFO",
            "propagate": False,
        },
        "notice": {
            "handlers": ["notice_file"],
            "level": "INFO",
            "propagate": False,
        },
        "tenure": {
            "handlers": ["tenure_file"],
            "level": "INFO",
            "propagate": False,
        },
    }