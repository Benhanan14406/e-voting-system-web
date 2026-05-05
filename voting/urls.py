from django.urls import path
from .views import CastVoteView, VoteConfirmationView

urlpatterns = [
    path("vote/<int:pk>/", CastVoteView.as_view(), name="vote"),
    path("vote/<int:pk>/confirmation/", VoteConfirmationView.as_view(), name="vote_confirmation"),
]