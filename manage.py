#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    from pathlib import Path
    from dotenv import load_dotenv

    # Load environment variables from .env
    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / ".env")

    # Map friendly short names or default to config.settings.development
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.development")
    if settings_module == "development":
        settings_module = "config.settings.development"
    elif settings_module == "production":
        settings_module = "config.settings.production"
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
