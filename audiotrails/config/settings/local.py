import socket

from .base import *  # noqa
from .base import INSTALLED_APPS, MIDDLEWARE, TEMPLATES

DEBUG = True
THUMBNAIL_DEBUG = True
TEMPLATES[0]["OPTIONS"]["debug"] = True

INSTALLED_APPS += ["silk"]

MIDDLEWARE = (
    ["whitenoise.runserver_nostatic"] + ["silk.middleware.SilkyMiddleware"] + MIDDLEWARE
)

# podman internal ips
INTERNAL_IPS = socket.gethostbyname_ex(socket.gethostname())[2]
