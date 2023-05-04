from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpResponse
from faker import Faker

from radiofeed.episodes.factories import create_episode
from radiofeed.users.factories import create_user

pytest_plugins = ["radiofeed.podcasts.fixtures"]


@pytest.fixture(autouse=True)
def settings_overrides(settings):
    """Default settings for all tests."""
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
    }
    settings.LOGGING = None
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(scope="session")
def faker():
    faker = Faker()
    yield faker
    faker.unique.clear()


@pytest.fixture
def locmem_cache(settings):
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    yield
    cache.clear()


@pytest.fixture(scope="session")
def get_response():
    return lambda req: HttpResponse()


@pytest.fixture
def user(db):
    return create_user()


@pytest.fixture
def anonymous_user():
    return AnonymousUser()


@pytest.fixture
def auth_user(client, user):
    client.force_login(user)
    return user


@pytest.fixture
def staff_user(db, client):
    user = create_user(is_staff=True)
    client.force_login(user)
    return user


@pytest.fixture
def episode(db):
    return create_episode()