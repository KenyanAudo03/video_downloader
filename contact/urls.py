from django.urls import path
from . import views

app_name = "contact"

urlpatterns = [
    path("submit-contact/", views.submit_contact, name="submit_contact"),
]
