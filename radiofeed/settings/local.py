from __future__ import annotations

from radiofeed.settings.base import *  # noqa
from radiofeed.settings.base import (
    ADMIN_SITE_HEADER,
    INSTALLED_APPS,
    MIDDLEWARE,
    configure_databases,
    configure_templates,
)

DEBUG = True

INTERNAL_IPS = ["127.0.0.1"]

INSTALLED_APPS += [
    "debug_toolbar",
    "django_browser_reload",
    "whitenoise.runserver_nostatic",
]

MIDDLEWARE += [
    "django_browser_reload.middleware.BrowserReloadMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

ADMIN_SITE_HEADER += " [DEVELOPMENT]"

DATABASES = configure_databases(conn_max_age=0)

TEMPLATES = configure_templates(debug=True)
