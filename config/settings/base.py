from pathlib import Path
from datetime import timedelta

# Corrected path calculation for being 3 folders deep now
BASE_DIR = Path(__file__).resolve().parent.parent.parent

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
    'rest_framework_simplejwt.token_blacklist'
]

MIDDLEWARE = [
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
        "django_file": {"class": "logging.FileHandler",
                        "filename": BASE_DIR / "logs/django.log", 
                        "formatter": "standard"},
        
        
        "error_file": {"class": "logging.FileHandler", "filename": BASE_DIR / "logs/errors.log", "formatter": "standard", "level": "ERROR"},
        "security_file": {"class": "logging.FileHandler", "filename": BASE_DIR / "logs/security.log", "formatter": "standard"},
        "certificate_file": {"class": "logging.FileHandler", "filename": BASE_DIR / "logs/certificate.log", "formatter": "standard"},
        "paper_file": {"class": "logging.FileHandler", "filename": BASE_DIR / "logs/pastpaper.log", "formatter": "standard"},
        "event_file": {"class": "logging.FileHandler", "filename": BASE_DIR / "logs/event.log", "formatter": "standard"},
        "notice_file": {"class": "logging.FileHandler", "filename": BASE_DIR / "logs/notice.log", "formatter": "standard"},
        "tenure_file": {"class": "logging.FileHandler", "filename": BASE_DIR / "logs/tenure.log", "formatter": "standard"},
    },
    "loggers": {
        "django": {"handlers": ["django_file", "error_file"], "level": "INFO", "propagate": True},
        "security": {"handlers": ["security_file"], "level": "INFO", "propagate": False},
        "certificate": {"handlers": ["certificate_file"], "level": "INFO", "propagate": False},
        "paper": {"handlers": ["paper_file"], "level": "INFO", "propagate": False},
        "event": {"handlers": ["event_file"], "level": "INFO", "propagate": False},  
        "notice": {"handlers": ["notice_file"], "level": "INFO", "propagate": False},
        "tenure": {"handlers": ["tenure_file"], "level": "INFO", "propagate": False},
    },
}