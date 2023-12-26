import http
import urllib.parse

import httpx
import pytest
from django.core.signing import Signer
from django.shortcuts import render
from django.urls import reverse

from radiofeed.tests.asserts import assert_200, assert_404


class TestManifest:
    @pytest.mark.django_db()
    def test_get(self, client):
        assert_200(client.get(reverse("manifest")))


class TestServiceWorker:
    @pytest.mark.django_db()
    def test_get(self, client):
        assert_200(client.get(reverse("service_worker")))


class TestFavicon:
    @pytest.mark.django_db()
    def test_get(self, client):
        assert_200(client.get(reverse("favicon")))


class TestRobots:
    @pytest.mark.django_db()
    def test_get(self, client):
        assert_200(client.get(reverse("robots")))


class TestHealthCheck:
    @pytest.mark.django_db()
    def test_get(self, client):
        assert_200(client.get(reverse("health_check")))


class TestSecurty:
    @pytest.mark.django_db()
    def test_get(self, client):
        assert_200(client.get(reverse("security")))


class TestAbout:
    @pytest.mark.django_db()
    def test_get(self, client):
        assert_200(client.get(reverse("about")))


class TestAcceptCookies:
    @pytest.mark.django_db()
    def test_post(self, client):
        response = client.post(reverse("accept_cookies"))
        assert_200(response)
        assert "accept-cookies" in response.cookies


class TestCoverImage:
    cover_url = "http://example.com/test.png"

    def get_url(self, size, url):
        return (
            reverse("cover_image", kwargs={"size": size})
            + "?"
            + urllib.parse.urlencode({"url": url})
        )

    def encode_url(self, url):
        return Signer().sign(url)

    @pytest.mark.django_db()
    def test_ok(self, client, db, mocker):
        def _handler(request):
            return httpx.Response(http.HTTPStatus.OK, content=b"")

        mock_client = httpx.Client(transport=httpx.MockTransport(_handler))
        mocker.patch("radiofeed.views.get_client", return_value=mock_client)
        mocker.patch("PIL.Image.open", return_value=mocker.Mock())
        assert_200(client.get(self.get_url(100, self.encode_url(self.cover_url))))

    @pytest.mark.django_db()
    def test_not_accepted_size(self, client, db, mocker):
        assert_404(client.get(self.get_url(500, self.encode_url(self.cover_url))))

    @pytest.mark.django_db()
    def test_missing_url_param(self, client, db, mocker):
        assert_404(client.get(reverse("cover_image", kwargs={"size": 100})))

    @pytest.mark.django_db()
    def test_unsigned_url(self, client, db):
        assert_404(client.get(self.get_url(100, self.cover_url)))

    @pytest.mark.django_db()
    def test_failed_download(self, client, db, mocker):
        def _handler(request):
            raise httpx.HTTPError("invalid")

        mock_client = httpx.Client(transport=httpx.MockTransport(_handler))
        mocker.patch("radiofeed.views.get_client", return_value=mock_client)

        assert_200(client.get(self.get_url(100, self.encode_url(self.cover_url))))

    @pytest.mark.django_db()
    def test_failed_process(self, client, db, mocker):
        def _handler(request):
            return httpx.Response(http.HTTPStatus.OK, content=b"")

        mock_client = httpx.Client(transport=httpx.MockTransport(_handler))
        mocker.patch("radiofeed.views.get_client", return_value=mock_client)
        mocker.patch("PIL.Image.open", side_effect=IOError())
        assert_200(client.get(self.get_url(100, self.encode_url(self.cover_url))))


class TestErrorPages:
    def test_bad_request(self, rf):
        assert_200(render(rf.get("/"), "400.html"))

    def test_not_found(self, rf):
        assert_200(render(rf.get("/"), "404.html"))

    def test_forbidden(self, rf):
        assert_200(render(rf.get("/"), "403.html"))

    def test_not_allowed(self, rf):
        assert_200(render(rf.get("/"), "405.html"))

    def test_server_error(self, rf):
        assert_200(render(rf.get("/"), "500.html"))

    def test_csrf(self, rf):
        assert_200(render(rf.get("/"), "403_csrf.html"))
