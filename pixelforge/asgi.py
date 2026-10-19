"""
ASGI config for pixelforge project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pixelforge.settings')
application = get_asgi_application()
