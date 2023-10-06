from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse

from radiofeed.htmx import render_htmx


def render_pagination(
    request: HttpRequest,
    object_list: QuerySet,
    template_name: str,
    extra_context: dict | None = None,
    *,
    page_size: int = 30,
    partial: str = "pagination",
    target: str = "pagination",
) -> HttpResponse:
    """Renders paginated object list."""

    return render_htmx(
        request,
        template_name,
        {
            "page_obj": Paginator(object_list, page_size).get_page(
                request.pagination.current
            ),
            "pagination_target": target,
            **(extra_context or {}),
        },
        partial=partial,
        target=target,
    )
