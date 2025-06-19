from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.download_page, name="download_page"),
]
