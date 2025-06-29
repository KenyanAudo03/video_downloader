from django.urls import path
from . import views

app_name = "audio"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search_youtube, name="search_youtube"),
    path('suggestions/', views.get_suggestions, name='get_suggestions'),
    path('<str:video_id>/', views.video_detail, name='video_detail')
]