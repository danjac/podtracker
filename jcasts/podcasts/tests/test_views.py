import pytest

from django.urls import reverse, reverse_lazy

from jcasts.episodes.factories import EpisodeFactory
from jcasts.podcasts.factories import (
    CategoryFactory,
    FollowFactory,
    PodcastFactory,
    RecommendationFactory,
)
from jcasts.podcasts.models import Follow
from jcasts.shared.assertions import assert_conflict, assert_not_found, assert_ok

podcasts_url = reverse_lazy("podcasts:index")


class TestPodcasts:
    def test_anonymous(self, client, db, django_assert_num_queries):
        PodcastFactory.create_batch(3, promoted=True)
        with django_assert_num_queries(3):
            resp = client.get(podcasts_url)
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 3

    def test_user_is_following_promoted(
        self, client, auth_user, django_assert_num_queries
    ):
        """If user is not following any podcasts, just show general feed"""

        PodcastFactory.create_batch(3, promoted=True)
        sub = FollowFactory(user=auth_user).podcast
        with django_assert_num_queries(6):
            resp = client.get(reverse("podcasts:index"), {"promoted": True})
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 3
        assert sub not in resp.context_data["page_obj"].object_list

    def test_user_is_not_following(self, client, auth_user, django_assert_num_queries):
        """If user is not following any podcasts, just show general feed"""

        PodcastFactory.create_batch(3, promoted=True)
        with django_assert_num_queries(6):
            resp = client.get(podcasts_url)
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 3

    def test_user_is_following(self, client, auth_user, django_assert_num_queries):
        """If user following any podcasts, show only own feed with these podcasts"""

        PodcastFactory.create_batch(3)
        sub = FollowFactory(user=auth_user)
        with django_assert_num_queries(6):
            resp = client.get(podcasts_url)
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 1
        assert resp.context_data["page_obj"].object_list[0] == sub.podcast


class TestLatest:
    def url(self, podcast):
        return reverse("podcasts:latest", args=[podcast.id])

    def test_has_no_episodes(self, client, podcast):
        resp = client.get(self.url(podcast))
        assert_not_found(resp)

    def test_has_episodes(self, client, episode):
        resp = client.get(self.url(episode.podcast))
        assert resp.url == episode.get_absolute_url()


class TestSearchPodcasts:
    def test_search_empty(self, client, db):
        assert (
            client.get(
                reverse("podcasts:search_podcasts"),
                {"q": ""},
            ).url
            == podcasts_url
        )

    def test_search(self, client, db, faker):
        podcast = PodcastFactory(title=faker.unique.text())
        PodcastFactory.create_batch(3, title="zzz", keywords="zzzz")
        resp = client.get(
            reverse("podcasts:search_podcasts"),
            {"q": podcast.title},
        )
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 1
        assert resp.context_data["page_obj"].object_list[0] == podcast


class TestSearchPodcastIndex:
    def test_search(self, client, db, mocker):
        mock_search = mocker.patch("jcasts.podcasts.podcastindex.search")

        resp = client.get(reverse("podcasts:search_podcastindex"), {"q": "test"})
        assert_ok(resp)

        mock_search.assert_called()


class TestPodcastRecommendations:
    def test_get(self, client, db, podcast):
        EpisodeFactory.create_batch(3, podcast=podcast)
        RecommendationFactory.create_batch(3, podcast=podcast)
        resp = client.get(
            reverse("podcasts:podcast_recommendations", args=[podcast.id, podcast.slug])
        )
        assert_ok(resp)
        assert resp.context_data["podcast"] == podcast
        assert len(resp.context_data["recommendations"]) == 3


class TestPodcastDetail:
    def test_get_podcast(self, client, podcast):
        resp = client.get(
            reverse("podcasts:podcast_detail", args=[podcast.id, podcast.slug])
        )
        assert_ok(resp)
        assert resp.context_data["podcast"] == podcast


class TestPodcastEpisodes:
    def test_get_episodes(self, client, podcast):
        EpisodeFactory.create_batch(3, podcast=podcast)

        resp = client.get(
            reverse(
                "podcasts:podcast_episodes",
                args=[podcast.id, podcast.slug],
            )
        )
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 3

    def test_get_oldest_first(self, client, podcast):
        EpisodeFactory.create_batch(3, podcast=podcast)

        resp = client.get(
            reverse(
                "podcasts:podcast_episodes",
                args=[podcast.id, podcast.slug],
            ),
            {"ordering": "asc"},
        )
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 3

    def test_search(self, client, podcast, faker):
        EpisodeFactory.create_batch(3, podcast=podcast)

        episode = EpisodeFactory(title=faker.unique.name(), podcast=podcast)

        resp = client.get(
            reverse(
                "podcasts:podcast_episodes",
                args=[podcast.id, podcast.slug],
            ),
            {"q": episode.title},
        )
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 1


class TestCategoryDetail:
    def test_get(self, client, category):
        CategoryFactory.create_batch(3, parent=category)
        PodcastFactory.create_batch(12, categories=[category])
        resp = client.get(category.get_absolute_url())
        assert_ok(resp)
        assert resp.context_data["category"] == category

    def test_get_episodes(self, client, category):

        CategoryFactory.create_batch(3, parent=category)
        PodcastFactory.create_batch(12, categories=[category])
        resp = client.get(category.get_absolute_url())
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 12

    def test_search(self, client, category, faker):

        CategoryFactory.create_batch(3, parent=category)
        PodcastFactory.create_batch(
            12, title="zzzz", keywords="zzzz", categories=[category]
        )
        podcast = PodcastFactory(title=faker.unique.text(), categories=[category])

        resp = client.get(category.get_absolute_url(), {"q": podcast.title})
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 1


class TestFollow:
    @pytest.fixture
    def url(self, podcast):
        return reverse("podcasts:follow", args=[podcast.id])

    def test_follow(self, client, podcast, auth_user, url):
        resp = client.post(url, {"render": True})
        assert_ok(resp)
        assert Follow.objects.filter(podcast=podcast, user=auth_user).exists()

    @pytest.mark.django_db(transaction=True)
    def test_already_following(self, client, podcast, auth_user, url):
        FollowFactory(user=auth_user, podcast=podcast)
        resp = client.post(url)
        assert_conflict(resp)
        assert Follow.objects.filter(podcast=podcast, user=auth_user).exists()


class TestUnfollow:
    def test_unfollow(self, client, auth_user, podcast):
        FollowFactory(user=auth_user, podcast=podcast)
        resp = client.post(reverse("podcasts:unfollow", args=[podcast.id]))
        assert_ok(resp)
        assert not Follow.objects.filter(podcast=podcast, user=auth_user).exists()
