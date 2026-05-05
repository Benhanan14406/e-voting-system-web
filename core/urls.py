from django.urls import path
from django.views.generic.base import RedirectView
from .views import dashboard

urlpatterns = [
    path("", RedirectView.as_view(url="dashboard/", permanent=False)),
    path("dashboard/", dashboard, name="dashboard"),
]