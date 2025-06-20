from django.urls import path
from . import views

urlpatterns = [
    path("", views.homepage, name="homepage"),
    path("load-videos/", views.load_videos, name="load_videos"),
    path("categories/", views.get_categories, name="get_categories"),
    path("clear-cache/", views.clear_video_cache, name="clear_cache"),
]
