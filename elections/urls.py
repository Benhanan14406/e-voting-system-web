from django.urls import path
from .views import ElectionListView, ElectionCreateView, ElectionOpenView, ElectionCloseView, CandidateListView, CandidateCreateView, CandidateDeleteView

urlpatterns = [
    path("elections/", ElectionListView.as_view(), name="election_list"),
    path("elections/new/", ElectionCreateView.as_view(), name="election_create"),
    path("elections/<uuid:pk>/open/", ElectionOpenView.as_view(), name="election_open"),
    path("elections/<uuid:pk>/close/", ElectionCloseView.as_view(), name="election_close"),
    path("elections/<uuid:pk>/candidates/", CandidateListView.as_view(), name="candidate_list"),
    path("elections/<uuid:pk>/candidates/add/", CandidateCreateView.as_view(), name="candidate_add"),
    path("candidates/<uuid:pk>/delete/", CandidateDeleteView.as_view(), name="candidate_delete"),
]