from django.contrib import admin
from django.urls import path, include
from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/get-video-info/", views.get_video_info, name="get_video_info"),
    path(
        "api/check-status/<uuid:download_id>/", views.check_status, name="check_status"
    ),
    path(
        "api/download/<uuid:download_id>/", views.download_video, name="download_video"
    ),
    path("api/history/", views.download_history, name="download_history"),
    path("download/<uuid:download_id>/", views.serve_download, name="serve_download"),
]
