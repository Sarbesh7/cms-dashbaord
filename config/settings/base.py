from pathlib import Path
from datetime import timedelta
import os

# Corrected path calculation for being 3 folders deep now
BASE_DIR = Path(__file__).resolve().parent.parent.parent

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
    'rest_framework.authtoken',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
CORS_ALLOW_ALL_ORIGINS = True

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
        'anon': '100/day',
        'user': '1000/day'
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
}

AUTH_USER_MODEL = "users.User"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
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