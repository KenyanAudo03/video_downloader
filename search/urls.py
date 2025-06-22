from django.urls import path
from . import views

app_name = "search"

urlpatterns = [
    # Main search pages
    path("results/", views.search_results, name="search_results"),
    # API endpoints
    path("search-video/", views.search_video, name="search_video"),
    # Utility endpoints
    path(
        "video-metadata/<str:video_id>/",
        views.get_video_metadata,
        name="video_metadata",
    ),
    path("suggest/", views.suggest_videos, name="suggest_videos"),
    path("api/track-play/", views.track_video_play, name="track_video_play"),
]
