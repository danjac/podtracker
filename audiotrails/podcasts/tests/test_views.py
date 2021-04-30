import http

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from audiotrails.episodes.factories import EpisodeFactory
from audiotrails.users.factories import UserFactory

from .. import itunes
from ..factories import (
    CategoryFactory,
    FollowFactory,
    PodcastFactory,
    RecommendationFactory,
)
from ..itunes import SearchResult
from ..models import Follow


def mock_fetch_itunes_genre(genre_id, num_results=20):
    return [
        SearchResult(
            rss="http://example.com/test.xml",
            itunes="https://apple.com/some-link",
            image="test.jpg",
            title="test title",
        )
    ], []


def mock_search_itunes(search_term, num_results=12):
    return [
        SearchResult(
            rss="http://example.com/test.xml",
            itunes="https://apple.com/some-link",
            image="test.jpg",
            title="test title",
        )
    ], []


class TestPodcastCoverImage(TestCase):
    def test_get(self):
        podcast = PodcastFactory()
        self.assertEqual(
            self.client.get(
                reverse("podcasts:podcast_cover_image", args=[podcast.id])
            ).status_code,
            http.HTTPStatus.OK,
        )


class AnonymousPodcastsTests(TestCase):
    def test_anonymous(self):
        PodcastFactory.create_batch(3, promoted=True)
        resp = self.client.get(reverse("podcasts:index"), HTTP_TURBO_FRAME="podcasts")
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 3)


class AuthenticatedPodcastsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self.client.force_login(self.user)

    def test_user_is_following_featured(self):
        """If user is not following any podcasts, just show general feed"""

        PodcastFactory.create_batch(3, promoted=True)
        sub = FollowFactory(user=self.user).podcast
        resp = self.client.get(
            reverse("podcasts:featured"), HTTP_TURBO_FRAME="podcasts"
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 3)
        self.assertFalse(sub in resp.context_data["page_obj"].object_list)

    def test_user_is_not_following(self):
        """If user is not following any podcasts, just show general feed"""

        PodcastFactory.create_batch(3, promoted=True)
        resp = self.client.get(reverse("podcasts:index"), HTTP_TURBO_FRAME="podcasts")
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 3)

    def test_user_is_following(self):
        """If user following any podcasts, show only own feed with these pdocasts"""

        PodcastFactory.create_batch(3)
        sub = FollowFactory(user=self.user)
        resp = self.client.get(reverse("podcasts:index"), HTTP_TURBO_FRAME="podcasts")
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 1)
        self.assertEqual(resp.context_data["page_obj"].object_list[0], sub.podcast)


class SearchPodcastsTests(TestCase):
    def test_search_empty(self):
        self.assertRedirects(
            self.client.get(
                reverse("podcasts:search_podcasts"),
                {"q": ""},
                HTTP_TURBO_FRAME="podcasts",
            ),
            reverse("podcasts:index"),
        )

    def test_search(self):
        podcast = PodcastFactory(title="testing")
        PodcastFactory.create_batch(3, title="zzz", keywords="zzzz")
        resp = self.client.get(
            reverse("podcasts:search_podcasts"),
            {"q": "testing"},
            HTTP_TURBO_FRAME="podcasts",
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 1)
        self.assertEqual(resp.context_data["page_obj"].object_list[0], podcast)


class PodcastRecommendationsTests(TestCase):
    def test_get(self):
        podcast = PodcastFactory()
        EpisodeFactory.create_batch(3, podcast=podcast)
        RecommendationFactory.create_batch(3, podcast=podcast)
        resp = self.client.get(
            reverse("podcasts:podcast_recommendations", args=[podcast.id, podcast.slug])
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(resp.context_data["podcast"], podcast)
        self.assertEqual(len(resp.context_data["recommendations"]), 3)


class PreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.podcast = PodcastFactory()

    def setUp(self):
        self.client.force_login(self.user)

    def test_not_turbo_frame(self):
        self.assertRedirects(
            self.client.get(reverse("podcasts:preview", args=[self.podcast.id])),
            self.podcast.get_absolute_url(),
        )

    def test_authenticated(self):
        EpisodeFactory.create_batch(3, podcast=self.podcast)
        resp = self.client.get(
            reverse("podcasts:preview", args=[self.podcast.id]),
            HTTP_TURBO_FRAME="modal",
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(resp.context_data["podcast"], self.podcast)
        self.assertFalse(resp.context_data["is_following"])

    def test_following(self):
        EpisodeFactory.create_batch(3, podcast=self.podcast)
        FollowFactory(podcast=self.podcast, user=self.user)
        resp = self.client.get(
            reverse("podcasts:preview", args=[self.podcast.id]),
            HTTP_TURBO_FRAME="modal",
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(resp.context_data["podcast"], self.podcast)
        self.assertTrue(resp.context_data["is_following"])


class PodcastEpisodeListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.podcast = PodcastFactory()
        EpisodeFactory.create_batch(3, podcast=cls.podcast)

    def test_legacy_redirect(self):
        resp = self.client.get(
            f"/podcasts/{self.podcast.id}/{self.podcast.slug}/episodes/"
        )
        self.assertRedirects(
            resp,
            reverse(
                "podcasts:podcast_episodes",
                args=[self.podcast.id, self.podcast.slug],
            ),
            status_code=http.HTTPStatus.MOVED_PERMANENTLY,
        )

    def test_get_podcast(self):
        resp = self.client.get(
            reverse(
                "podcasts:podcast_episodes",
                args=[self.podcast.id, self.podcast.slug],
            )
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(resp.context_data["podcast"], self.podcast)

    def test_get_episodes(self):
        resp = self.client.get(
            reverse(
                "podcasts:podcast_episodes",
                args=[self.podcast.id, self.podcast.slug],
            ),
            HTTP_TURBO_FRAME="episodes",
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 3)

    def test_search(self):
        EpisodeFactory(title="testing", podcast=self.podcast)
        resp = self.client.get(
            reverse(
                "podcasts:podcast_episodes",
                args=[self.podcast.id, self.podcast.slug],
            ),
            {"q": "testing"},
            HTTP_TURBO_FRAME="episodes",
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 1)


class CategoryListTests(TestCase):
    def test_get(self):
        parents = CategoryFactory.create_batch(3, parent=None)
        c1 = CategoryFactory(parent=parents[0])
        c2 = CategoryFactory(parent=parents[1])
        c3 = CategoryFactory(parent=parents[2])

        PodcastFactory(categories=[c1, parents[0]])
        PodcastFactory(categories=[c2, parents[1]])
        PodcastFactory(categories=[c3, parents[2]])

        resp = self.client.get(reverse("podcasts:categories"))
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["categories"]), 3)

    def test_search(self):
        parents = CategoryFactory.create_batch(3, parent=None)
        c1 = CategoryFactory(parent=parents[0])
        c2 = CategoryFactory(parent=parents[1])
        c3 = CategoryFactory(parent=parents[2], name="testing child")

        c4 = CategoryFactory(name="testing parent")

        PodcastFactory(categories=[c1])
        PodcastFactory(categories=[c2])
        PodcastFactory(categories=[c3])
        PodcastFactory(categories=[c4])

        resp = self.client.get(reverse("podcasts:categories"), {"q": "testing"})
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["categories"]), 2)


class TestCategoryDetail:
    def test_get(self, client, category):

        CategoryFactory.create_batch(3, parent=category)
        PodcastFactory.create_batch(12, categories=[category])
        resp = client.get(category.get_absolute_url())
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(resp.context_data["category"], category)

    def test_get_episodes(self, client, category):

        CategoryFactory.create_batch(3, parent=category)
        PodcastFactory.create_batch(12, categories=[category])
        resp = client.get(category.get_absolute_url(), HTTP_TURBO_FRAME="podcasts")
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 12)

    def test_search(self, client, category):

        CategoryFactory.create_batch(3, parent=category)
        PodcastFactory.create_batch(
            12, title="zzzz", keywords="zzzz", categories=[category]
        )
        PodcastFactory(title="testing", categories=[category])

        resp = client.get(
            category.get_absolute_url(), {"q": "testing"}, HTTP_TURBO_FRAME="podcasts"
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertEqual(len(resp.context_data["page_obj"].object_list), 1)


class FollowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.podcast = PodcastFactory()

    def login_user(self):
        user = UserFactory()
        self.client.force_login(user)
        return user

    def test_anonymous(self):
        self.assertRedirects(
            self.client.post(reverse("podcasts:follow", args=[self.podcast.id])),
            f"{reverse('account_login')}?next={self.podcast.get_absolute_url()}",
        )

    def test_subscribe(self):
        user = self.login_user()
        self.client.force_login(user)
        resp = self.client.post(reverse("podcasts:follow", args=[self.podcast.id]))
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertTrue(Follow.objects.filter(podcast=self.podcast, user=user).exists())

    def test_already_following(self):
        user = self.login_user()
        FollowFactory(user=user, podcast=self.podcast)
        self.assertEqual(
            self.client.post(
                reverse("podcasts:follow", args=[self.podcast.id])
            ).status_code,
            http.HTTPStatus.OK,
        )


class UnfollowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.podcast = PodcastFactory()

    def test_anonymous(self):
        self.assertRedirects(
            self.client.post(reverse("podcasts:unfollow", args=[self.podcast.id])),
            f"{reverse('account_login')}?next={self.podcast.get_absolute_url()}",
        )

    def test_unsubscribe(self):
        user = UserFactory()
        self.client.force_login(user)
        FollowFactory(user=user, podcast=self.podcast)
        resp = self.client.post(reverse("podcasts:unfollow", args=[self.podcast.id]))
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertFalse(
            Follow.objects.filter(podcast=self.podcast, user=user).exists()
        )


class ITunesCategoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = CategoryFactory(itunes_genre_id=1200)

    @patch(
        "audiotrails.podcasts.views.sync_podcast_feed.delay",
    )
    @patch.object(
        itunes,
        "fetch_itunes_genre",
        mock_fetch_itunes_genre,
    )
    def test_get(self, mock):
        resp = self.client.get(
            reverse("podcasts:itunes_category", args=[self.category.id]),
        )

        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertFalse(resp.context_data["error"])
        self.assertEqual(len(resp.context_data["results"]), 1)
        self.assertEqual(resp.context_data["results"][0].title, "test title")

    @patch.object(
        itunes, "fetch_itunes_genre", side_effect=itunes.Invalid, autospec=True
    )
    def test_invalid_results(self, mock):

        resp = self.client.get(
            reverse("podcasts:itunes_category", args=[self.category.id])
        )

        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertTrue(resp.context_data["error"])
        self.assertEqual(len(resp.context_data["results"]), 0)


class SearchITunesTests(TestCase):
    def test_search_is_empty(self):
        resp = self.client.get(reverse("podcasts:search_itunes"))
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertFalse(resp.context_data["error"])
        self.assertEqual(len(resp.context_data["results"]), 0)

    @patch(
        "audiotrails.podcasts.views.sync_podcast_feed.delay",
    )
    @patch.object(itunes, "search_itunes", mock_search_itunes)
    def test_search(self, mock):
        resp = self.client.get(reverse("podcasts:search_itunes"), {"q": "test"})

        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertFalse(resp.context_data["error"])
        self.assertEqual(len(resp.context_data["results"]), 1)
        self.assertEqual(resp.context_data["results"][0].title, "test title")

    @patch.object(itunes, "search_itunes", side_effect=itunes.Invalid, autospec=True)
    def test_invalid_results(self, mock):
        resp = self.client.get(reverse("podcasts:search_itunes"), {"q": "testing"})
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        self.assertTrue(resp.context_data["error"])
        self.assertEqual(len(resp.context_data["results"]), 0)
