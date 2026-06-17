from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import timedelta

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")




# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-key-change-me")

DEBUG = True

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,[::1]",
    ).split(",")
    if host.strip()
]


# Application definition

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
    # 'apps.logs',
    # 'corsheaders',
]

MIDDLEWARE = [
    # 'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# --- Updated Database Configuration ---


#database url from environment variable or default to local use here !!(<._.>)!!hehe
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',

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
    
}

AUTH_USER_MODEL = "users.User"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = "swikrityac31@gmail.com"
EMAIL_HOST_PASSWORD = "xvmz fpzx eykp gzop"


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = 'media/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "http://127.0.0.1:3000",
# ]

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "standard": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },

    "handlers": {
        "django_file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/django.log",
            "formatter": "standard",
        },

        "error_file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/errors.log",
            "formatter": "standard",
            "level": "ERROR",
        },

        "security_file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/security.log",
            "formatter": "standard",
        },

        "certificate_file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/certificate.log",
            "formatter": "standard",
        },
        
        "paper_file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/pastpaper.log",
            "formatter": "standard",
        },
        "event_file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/event.log",
            "formatter": "standard",
        },
        "notice_file": {
                "class": "logging.FileHandler",
                "filename": BASE_DIR / "logs/notice.log",
                "formatter": "standard",
            },
        "tenure_file": {
                "class": "logging.FileHandler",
                "filename": BASE_DIR / "logs/tenure.log",
                "formatter": "standard",
            },
        
    },

    "loggers": {
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
        
    },
}
