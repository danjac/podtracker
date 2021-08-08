import pytest

from django.urls import reverse, reverse_lazy

from jcasts.episodes.factories import (
    AudioLogFactory,
    EpisodeFactory,
    FavoriteFactory,
    QueueItemFactory,
)
from jcasts.episodes.middleware import Player
from jcasts.episodes.models import AudioLog, Episode, Favorite, QueueItem
from jcasts.podcasts.factories import FollowFactory, PodcastFactory
from jcasts.shared.assertions import (
    assert_bad_request,
    assert_conflict,
    assert_no_content,
    assert_ok,
)

episodes_url = reverse_lazy("episodes:index")


def _is_playing(client, episode):
    return client.session.get(Player.session_key) == episode.id


class TestNewEpisodes:
    def test_anonymous_user(self, client, db):
        self._test_no_follows(client)

    def test_no_follows(self, client, db, auth_user):
        self._test_no_follows(client)

    def test_user_has_follows(self, client, auth_user):
        promoted = PodcastFactory(promoted=True)
        EpisodeFactory(podcast=promoted)

        EpisodeFactory.create_batch(3)

        episode = EpisodeFactory()
        FollowFactory(user=auth_user, podcast=episode.podcast)

        resp = client.get(episodes_url)
        assert_ok(resp)
        assert not resp.context_data["promoted"]
        assert resp.context_data["has_follows"]
        assert len(resp.context_data["page_obj"].object_list) == 1
        assert resp.context_data["page_obj"].object_list[0] == episode

    def test_user_has_follows_promoted(self, client, auth_user):
        promoted = PodcastFactory(promoted=True)
        EpisodeFactory(podcast=promoted)

        EpisodeFactory.create_batch(3)

        episode = EpisodeFactory()
        FollowFactory(user=auth_user, podcast=episode.podcast)

        resp = client.get(reverse("episodes:index"), {"promoted": True})

        assert_ok(resp)
        assert resp.context_data["promoted"]
        assert resp.context_data["has_follows"]
        assert len(resp.context_data["page_obj"].object_list) == 1
        assert resp.context_data["page_obj"].object_list[0].podcast == promoted

    def _test_no_follows(self, client):
        promoted = PodcastFactory(promoted=True)
        EpisodeFactory(podcast=promoted)
        EpisodeFactory.create_batch(3)
        resp = client.get(episodes_url)
        assert_ok(resp)
        assert not resp.context_data["has_follows"]
        assert len(resp.context_data["page_obj"].object_list) == 1


class TestSearchEpisodes:
    url = reverse_lazy("episodes:search_episodes")

    def test_page(self, db, client):
        resp = client.get(self.url, {"q": "test"})
        assert_ok(resp)

    def test_search_empty(self, db, client):
        assert client.get(self.url, {"q": ""}).url == reverse("episodes:index")

    def test_search(self, db, client, faker):
        EpisodeFactory.create_batch(3, title="zzzz", keywords="zzzz")
        episode = EpisodeFactory(title=faker.unique.name())
        resp = client.get(
            self.url,
            {"q": episode.title},
        )
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 1
        assert resp.context_data["page_obj"].object_list[0] == episode


class TestEpisodeDetail:
    def test_detail(self, client, episode):
        resp = client.get(episode.get_absolute_url())
        assert_ok(resp)
        assert resp.context_data["episode"] == episode


class TestEpisodeActions:
    def test_actions(self, client, auth_user, episode):
        resp = client.get(
            reverse("episodes:actions", args=[episode.id]),
        )
        assert_ok(resp)
        assert resp.context_data["episode"] == episode


class TestReloadPlayer:
    url = reverse_lazy("episodes:reload_player")

    def test_player_empty(self, client, auth_user):
        assert_ok(client.get(self.url))

    def test_player_not_empty(self, client, auth_user, player_episode):
        assert_ok(client.get(self.url))


class TestStartPlayer:
    def url(self, episode):
        return reverse("episodes:start_player", args=[episode.id])

    def test_play_from_start(self, client, auth_user, episode):
        assert_ok(client.post(self.url(episode)))

        assert AudioLog.objects.filter(user=auth_user, episode=episode).exists()
        assert client.session[Player.session_key] == episode.id

    def test_another_episode_in_player(self, client, auth_user, episode):
        client.session[Player.session_key] = EpisodeFactory().id

        assert_ok(client.post(self.url(episode)))

        assert AudioLog.objects.filter(user=auth_user, episode=episode).exists()

        assert client.session[Player.session_key] == episode.id

    def test_resume(self, client, auth_user, episode):
        log = AudioLogFactory(user=auth_user, episode=episode, current_time=2000)
        assert_ok(client.post(self.url(episode)))

        log.refresh_from_db()

        assert log.current_time == 2000
        assert client.session[Player.session_key] == episode.id


class TestPlayNextEpisode:
    url = reverse_lazy("episodes:play_next_episode")

    def test_has_next_in_queue(self, client, auth_user, player_episode):

        episode = EpisodeFactory()

        previous = AudioLogFactory(user=auth_user, episode=player_episode)

        QueueItemFactory(user=auth_user, episode=episode)
        resp = client.post(self.url)

        assert_ok(resp)

        assert QueueItem.objects.count() == 0

        assert AudioLog.objects.filter(user=auth_user, episode=episode).exists()

        previous.refresh_from_db()

        assert previous.completed
        assert previous.current_time == 0

        assert not _is_playing(client, previous)
        assert _is_playing(client, episode)

    def test_has_next_in_queue_if_autoplay_disabled(
        self, client, auth_user, player_episode
    ):

        episode = EpisodeFactory()
        previous = AudioLogFactory(user=auth_user, episode=player_episode)

        auth_user.autoplay = False
        auth_user.save()

        QueueItemFactory(user=auth_user, episode=episode)
        resp = client.post(self.url)

        assert_ok(resp)
        assert QueueItem.objects.count() == 1

        assert not AudioLog.objects.filter(user=auth_user, episode=episode).exists()

        previous.refresh_from_db()

        assert not _is_playing(client, episode)
        assert not _is_playing(client, previous.episode)

        assert previous.completed
        assert previous.current_time == 0

    def test_has_next_in_queue_if_autoplay_enabled(
        self, client, auth_user, player_episode
    ):

        episode = EpisodeFactory()
        QueueItemFactory(user=auth_user, episode=episode)

        previous = AudioLogFactory(
            user=auth_user, current_time=2000, episode=player_episode
        )

        resp = client.post(self.url)
        assert_ok(resp)

        previous.refresh_from_db()

        assert previous.completed
        assert previous.current_time == 0

        assert not _is_playing(client, previous)
        assert _is_playing(client, episode)

    def test_queue_empty(self, client, auth_user, player_episode):

        previous = AudioLogFactory(
            user=auth_user, current_time=2000, episode=player_episode
        )

        resp = client.post(self.url)
        assert_ok(resp)
        assert QueueItem.objects.count() == 0

        previous.refresh_from_db()

        assert previous.completed
        assert previous.current_time == 0

        assert not _is_playing(client, previous)


class TestClosePlayer:
    url = reverse_lazy("episodes:close_player")

    def test_stop_if_player_empty(self, client, auth_user):
        resp = client.post(self.url)
        assert_ok(resp)

    def test_stop(self, client, auth_user, player_episode):

        log = AudioLogFactory(user=auth_user, current_time=2000, episode=player_episode)

        resp = client.post(self.url)
        assert_ok(resp)

        # do not mark complete
        log.refresh_from_db()

        assert not log.completed
        assert log.current_time == 2000

        assert not _is_playing(client, player_episode)


class TestPlayerTimeUpdate:
    url = reverse_lazy("episodes:player_time_update")

    @pytest.fixture
    def log(self, auth_user, player_episode):
        return AudioLogFactory(user=auth_user, episode=player_episode)

    def test_is_running(self, client, auth_user, log):

        resp = client.post(
            self.url,
            {"current_time": "1030"},
        )
        assert_no_content(resp)

        log.refresh_from_db()
        assert log.current_time == 1030

    def test_player_not_running(self, client, auth_user, episode):
        resp = client.post(
            self.url,
            {"current_time": "1030"},
        )
        assert_no_content(resp)

    def test_missing_data(self, client, auth_user, log):

        resp = client.post(self.url)
        assert_bad_request(resp)

    def test_invalid_data(self, client, auth_user, log):

        resp = client.post(self.url, {"current_time": "xyz"})
        assert_bad_request(resp)


class TestHistory:
    url = reverse_lazy("episodes:history")

    def test_get(self, client, auth_user):
        AudioLogFactory.create_batch(3, user=auth_user)
        resp = client.get(self.url)
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 3

    def test_search(self, client, auth_user):

        podcast = PodcastFactory(title="zzzz", keywords="zzzzz")

        for _ in range(3):
            AudioLogFactory(
                user=auth_user,
                episode=EpisodeFactory(title="zzzz", keywords="zzzzz", podcast=podcast),
            )

        AudioLogFactory(user=auth_user, episode=EpisodeFactory(title="testing"))
        resp = client.get(self.url, {"q": "testing"})
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 1


class TestFavorites:
    url = reverse_lazy("episodes:favorites")

    def test_get(self, client, auth_user):
        FavoriteFactory.create_batch(3, user=auth_user)
        resp = client.get(self.url)

        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 3

    def test_search(self, client, auth_user):

        podcast = PodcastFactory(title="zzzz", keywords="zzzzz")

        for _ in range(3):
            FavoriteFactory(
                user=auth_user,
                episode=EpisodeFactory(title="zzzz", keywords="zzzzz", podcast=podcast),
            )

        FavoriteFactory(user=auth_user, episode=EpisodeFactory(title="testing"))

        resp = client.get(self.url, {"q": "testing"})
        assert_ok(resp)
        assert len(resp.context_data["page_obj"].object_list) == 1


class TestAddFavorite:
    def test_post(self, client, auth_user, episode):
        resp = client.post(reverse("episodes:add_favorite", args=[episode.id]))

        assert_no_content(resp)
        assert Favorite.objects.filter(user=auth_user, episode=episode).exists()

    @pytest.mark.django_db(transaction=True)
    def test_already_favorite(self, client, auth_user, episode):
        FavoriteFactory(episode=episode, user=auth_user)
        resp = client.post(reverse("episodes:add_favorite", args=[episode.id]))
        assert_conflict(resp)
        assert Favorite.objects.filter(user=auth_user, episode=episode).exists()


class TestRemoveFavorite:
    def test_post(self, client, auth_user, episode):
        FavoriteFactory(user=auth_user, episode=episode)
        resp = client.post(reverse("episodes:remove_favorite", args=[episode.id]))
        assert_no_content(resp)
        assert not Favorite.objects.filter(user=auth_user, episode=episode).exists()


class TestRemoveAudioLog:
    def url(self, episode: Episode) -> str:
        return reverse("episodes:remove_audio_log", args=[episode.id])

    def test_ok(self, client, auth_user, episode):
        AudioLogFactory(user=auth_user, episode=episode)
        AudioLogFactory(user=auth_user)
        assert_no_content(client.post(self.url(episode)))
        assert not AudioLog.objects.filter(user=auth_user, episode=episode).exists()
        assert AudioLog.objects.filter(user=auth_user).count() == 1

    def test_is_playing(self, client, auth_user, player_episode):
        """Do not remove log if episode is currently playing"""
        log = AudioLogFactory(user=auth_user, episode=player_episode)
        assert_no_content(client.post(self.url(log.episode)))
        assert AudioLog.objects.filter(user=auth_user, episode=log.episode).exists()

    def test_none_remaining(self, client, auth_user, episode):
        log = AudioLogFactory(user=auth_user, episode=episode)
        assert_no_content(client.post(self.url(log.episode)))
        assert not AudioLog.objects.filter(user=auth_user, episode=episode).exists()
        assert AudioLog.objects.filter(user=auth_user).count() == 0


class TestQueue:
    def test_get(self, client, auth_user):
        QueueItemFactory.create_batch(3, user=auth_user)
        assert_ok(client.get(reverse("episodes:queue")))


class TestAddToQueue:
    add_to_start_url = "episodes:add_to_queue_start"
    add_to_end_url = "episodes:add_to_queue_end"

    def test_add_to_queue_end(self, client, auth_user):
        first = EpisodeFactory()
        second = EpisodeFactory()
        third = EpisodeFactory()

        for episode in (first, second, third):
            resp = client.post(reverse(self.add_to_end_url, args=[episode.id]))
            assert_no_content(resp)

        items = (
            QueueItem.objects.filter(user=auth_user)
            .select_related("episode")
            .order_by("position")
        )

        assert items[0].episode == first
        assert items[0].position == 1

        assert items[1].episode, second
        assert items[1].position == 2

        assert items[2].episode, third
        assert items[2].position == 3

    def test_add_to_queue_start(self, client, auth_user):
        first = EpisodeFactory()
        second = EpisodeFactory()
        third = EpisodeFactory()

        for episode in (first, second, third):
            resp = client.post(
                reverse(
                    self.add_to_start_url,
                    args=[episode.id],
                ),
            )
            assert_no_content(resp)

        items = (
            QueueItem.objects.filter(user=auth_user)
            .select_related("episode")
            .order_by("position")
        )

        assert items[0].episode == third
        assert items[0].position == 1

        assert items[1].episode, second
        assert items[1].position == 2

        assert items[2].episode, first
        assert items[2].position == 3

    def test_is_playing(self, client, auth_user, player_episode):
        resp = client.post(
            reverse(
                self.add_to_start_url,
                args=[player_episode.id],
            ),
        )
        assert_bad_request(resp)
        assert QueueItem.objects.count() == 0

    @pytest.mark.django_db(transaction=True)
    def test_already_queued(self, client, auth_user, episode):
        QueueItemFactory(episode=episode, user=auth_user)
        resp = client.post(
            reverse(
                self.add_to_start_url,
                args=[episode.id],
            ),
        )
        assert_conflict(resp)


class TestRemoveFromQueue:
    def test_post(self, client, auth_user):
        item = QueueItemFactory(user=auth_user)
        resp = client.post(
            reverse("episodes:remove_from_queue", args=[item.episode.id])
        )

        assert_no_content(resp)
        assert QueueItem.objects.filter(user=auth_user).count() == 0


class TestMoveQueueItems:
    def test_post(self, client, auth_user):

        first = QueueItemFactory(user=auth_user)
        second = QueueItemFactory(user=auth_user)
        third = QueueItemFactory(user=auth_user)

        items = QueueItem.objects.filter(user=auth_user).order_by("position")

        assert items[0] == first
        assert items[1] == second
        assert items[2] == third

        resp = client.post(
            reverse("episodes:move_queue_items"),
            {
                "items": [
                    third.id,
                    first.id,
                    second.id,
                ]
            },
        )

        assert_no_content(resp)

        items = QueueItem.objects.filter(user=auth_user).order_by("position")

        assert items[0] == third
        assert items[1] == first
        assert items[2] == second

    def test_invalid(self, client, auth_user):
        resp = client.post(reverse("episodes:move_queue_items"), {"items": "incorrect"})

        assert_bad_request(resp)


class TestMarkComplete:
    def test_mark_complete(self, client, auth_user, episode):

        log = AudioLogFactory(
            user=auth_user,
            episode=episode,
            completed=None,
            current_time=600,
        )

        assert_no_content(
            client.post(reverse("episodes:mark_complete", args=[episode.id]))
        )
        log.refresh_from_db()

        assert log.completed
        assert log.current_time == 0

    def test_is_playing(self, client, auth_user, player_episode):
        """Do not remove log if episode is currently playing"""
        log = AudioLogFactory(
            user=auth_user,
            episode=player_episode,
            completed=None,
            current_time=600,
        )

        assert_no_content(
            client.post(reverse("episodes:mark_complete", args=[log.episode.id]))
        )

        log.refresh_from_db()
        assert not log.completed
        assert log.current_time == 600
