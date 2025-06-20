from django.urls import path
from . import views

app_name = 'search'
urlpatterns = [
    path('', views.search_form, name='search_form'),  # Main search page
    path('results/', views.search_results, name='search_results'),  # Results page
    path('search-video/', views.search_video, name='search_video'),  # API endpoint (if needed)
]