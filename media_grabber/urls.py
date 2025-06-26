from django.urls import path
from . import views

app_name = 'media'

urlpatterns = [
    path('', views.media_grabber, name='index'),
    path('api/extract/', views.extract_video, name='extract_video'),  # This matches your frontend
    path('api/download/', views.extract_video, name='download_video'), # Keep for backward compatibility
]