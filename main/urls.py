from django.urls import path
from . import views
from share.views import shared_link

urlpatterns = [
    path("", views.homepage, name="homepage"),
    path("privacy_policy/", views.privacy_policy, name="privacy_policy"),
    path("terms_of_service/", views.terms_of_service, name="terms_of_service"),
    path("contact/", views.contact, name="contact"),
    path("load-videos/", views.load_videos, name="load_videos"),
    path("<str:video_id>/", shared_link, name="shared_link"),
]
