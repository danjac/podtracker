# Standard Library
import os

from django.core.asgi import get_asgi_application  # noqa isort:skip

# django app has to be initialized first
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "radiofeed.config.settings.local"
)  # noqa isort:skip

django_asgi_app = get_asgi_application()  # noqa isort:skip

from django.urls import re_path  # noqa isort:skip

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa isort:skip
from channels.sessions import SessionMiddlewareStack  # noqa isort:skip

from radiofeed.episodes.consumers import PlayerConsumer  # noqa isort:skip


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": SessionMiddlewareStack(
            URLRouter([re_path(r"ws/player/$", PlayerConsumer.as_asgi())])
        ),
    }
)
