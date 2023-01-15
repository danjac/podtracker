from __future__ import annotations

import functools

from collections.abc import Callable
from typing import Concatenate, ParamSpec

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django_htmx.http import HttpResponseClientRedirect

from radiofeed.response import HttpResponseUnauthorized

P = ParamSpec("P")

require_form_methods = require_http_methods(["GET", "POST"])


def require_auth(
    view: Callable[Concatenate[HttpRequest, P], HttpResponse]
) -> Callable[Concatenate[HttpRequest, P], HttpResponse]:
    """Login required decorator also handling HTMX and AJAX views."""

    @functools.wraps(view)
    def _wrapper(
        request: HttpRequest, *args: P.args, **kwargs: P.kwargs
    ) -> HttpResponse:
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)

        if request.htmx:
            return HttpResponseClientRedirect(
                redirect_to_login(settings.LOGIN_REDIRECT_URL).url
            )

        # plain non-HTMX AJAX: return a 401
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return HttpResponseUnauthorized()

        return redirect_to_login(request.get_full_path())

    return _wrapper
