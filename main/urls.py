from django.urls import path
from . import views
from share.views import shared_link

urlpatterns = [
    path("", views.homepage, name="homepage"),
    path("load-videos/", views.load_videos, name="load_videos"),

    path("<str:video_id>/", shared_link, name="shared_link"),
]
