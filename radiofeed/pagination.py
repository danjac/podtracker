from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import HttpRequest
from django.template.response import TemplateResponse
from django.utils.functional import SimpleLazyObject

from radiofeed.htmx import render_template_partial


def paginate(
    request: HttpRequest,
    object_list: QuerySet,
    page_size: int = settings.PAGE_SIZE,
    param: str = "page",
    **pagination_kwargs,
) -> SimpleLazyObject:
    """Returns paginated object list. This is resolved lazily, so
    the database query is only evaluated when referenced in template."""
    return SimpleLazyObject(
        lambda: Paginator(object_list, page_size).get_page(
            request.GET.get(param, ""),
            **pagination_kwargs,
        )
    )


def render_pagination_response(
    request: HttpRequest,
    object_list: QuerySet,
    template_name: str,
    extra_context: dict | None = None,
    pagination_kwargs: dict | None = None,
    **response_kwargs,
) -> TemplateResponse:
    """Shortcut function to render a paginated object list to template."""
    return render_template_partial(
        request,
        template_name,
        {
            "page_obj": paginate(request, object_list, **(pagination_kwargs or {})),
        }
        | (extra_context or {}),
        partial="pagination",
        target="pagination",
        **response_kwargs,
    )
