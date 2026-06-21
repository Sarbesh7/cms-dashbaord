import os
from django.core.asgi import get_asgi_application

# Update this line to point to production
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

application = get_asgi_application()