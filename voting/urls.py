from django.urls import path
from .views import CastVoteView, VoteConfirmationView

urlpatterns = [
    path("vote/<uuid:pk>/", CastVoteView.as_view(), name="vote"),
    path("vote/<uuid:pk>/confirmation/", VoteConfirmationView.as_view(), name="vote_confirmation"),
]