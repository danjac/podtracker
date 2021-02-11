from django.urls import path

from . import views

app_name = "podcasts"

urlpatterns = [
    path("", views.landing_page, name="landing_page"),
    path("podcasts/", views.podcasts, name="index"),
    path("search/podcasts/", views.search_podcasts, name="search_podcasts"),
    path("search/itunes/", views.search_itunes, name="search_itunes"),
    path("podcasts/<int:podcast_id>/actions/", views.podcast_actions, name="actions"),
    path("podcasts/<int:podcast_id>/~subscribe/", views.subscribe, name="subscribe"),
    path(
        "podcasts/<int:podcast_id>/~unsubscribe/", views.unsubscribe, name="unsubscribe"
    ),
    path(
        "podcasts/<int:podcast_id>/cover-image/",
        views.podcast_cover_image,
        name="podcast_cover_image",
    ),
    path(
        "podcasts/<int:podcast_id>/<slug:slug>/similar/",
        views.podcast_recommendations,
        name="podcast_recommendations",
    ),
    path(
        "podcasts/<int:podcast_id>/<slug:slug>/about/",
        views.podcast_detail,
        name="podcast_detail",
    ),
    path(
        "podcasts/<int:podcast_id>/<slug:slug>/",
        views.podcast_episodes,
        name="podcast_episodes",
    ),
    path("discover/", views.categories, name="categories"),
    path(
        "discover/<int:category_id>/itunes/",
        views.itunes_category,
        name="itunes_category",
    ),
    path(
        "discover/<int:category_id>/<slug:slug>/",
        views.category_detail,
        name="category_detail",
    ),
]
