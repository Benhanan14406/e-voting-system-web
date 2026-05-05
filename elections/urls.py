from django.urls import path
from .views import ElectionListView, ElectionCreateView, ElectionOpenView, ElectionCloseView, CandidateListView, CandidateCreateView, CandidateDeleteView

urlpatterns = [
    path("elections/", ElectionListView.as_view(), name="election_list"),
    path("elections/new/", ElectionCreateView.as_view(), name="election_create"),
    path("elections/<int:pk>/open/", ElectionOpenView.as_view(), name="election_open"),
    path("elections/<int:pk>/close/", ElectionCloseView.as_view(), name="election_close"),
    path("elections/<int:pk>/candidates/", CandidateListView.as_view(), name="candidate_list"),
    path("elections/<int:pk>/candidates/add/", CandidateCreateView.as_view(), name="candidate_add"),
    path("candidates/<int:pk>/delete/", CandidateDeleteView.as_view(), name="candidate_delete"),
]