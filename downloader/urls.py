from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/get-video-info/", views.get_video_info, name="get_video_info"),
    path("api/check-status/<str:download_id>/", views.check_status, name="check_status"),
    path("api/download/<str:download_id>/", views.download_video, name="download_video"),
    path("download/<str:download_id>/", views.serve_download, name="serve_download"),
]