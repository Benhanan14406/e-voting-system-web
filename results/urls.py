from django.urls import path
from .views import ResultsView

urlpatterns = [
    path("results/<uuid:pk>/", ResultsView.as_view(), name="results"),
]