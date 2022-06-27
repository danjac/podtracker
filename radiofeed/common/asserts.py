import functools
import http


def assert_status(response, status):
    assert response.status_code == status, response.content  # nosec


assert_bad_request = functools.partial(
    assert_status, status=http.HTTPStatus.BAD_REQUEST
)

assert_conflict = functools.partial(assert_status, status=http.HTTPStatus.CONFLICT)

assert_forbidden = functools.partial(assert_status, status=http.HTTPStatus.FORBIDDEN)

assert_gone = functools.partial(assert_status, status=http.HTTPStatus.GONE)

assert_no_content = functools.partial(assert_status, status=http.HTTPStatus.NO_CONTENT)

assert_not_found = functools.partial(assert_status, status=http.HTTPStatus.NOT_FOUND)

assert_ok = functools.partial(assert_status, status=http.HTTPStatus.OK)

assert_unauthorized = functools.partial(
    assert_status, status=http.HTTPStatus.UNAUTHORIZED
)
