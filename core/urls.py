from django.urls import path
from django.views.generic.base import RedirectView
from .views import dashboard, search_elections

urlpatterns = [
    path("", RedirectView.as_view(url="dashboard/", permanent=False)),
    path("dashboard/", dashboard, name="dashboard"),
    path("search/", search_elections, name="search_elections"),
]