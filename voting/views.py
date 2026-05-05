from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.contrib import messages
from elections.models import Election, Candidate
from .models import Vote
from .forms import VoteForm
from audit.utils import log_action


class VoterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == "voter"


class CastVoteView(VoterRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk, status="open")

        if Vote.objects.filter(election=election, voter=request.user).exists():
            messages.warning(request, "You have already voted in this election.")
            return redirect("dashboard")

        form = VoteForm(election=election)
        return render(request, "voting/vote.html", {
            "election": election,
            "form": form,
        })

    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk, status="open")

        if Vote.objects.filter(election=election, voter=request.user).exists():
            log_action(request, "DOUBLE_VOTE_ATTEMPT", f"User {request.user} tried to vote twice in election {pk}")
            messages.warning(request, "You have already voted in this election.")
            return redirect("dashboard")

        form = VoteForm(request.POST, election=election)
        if not form.is_valid():
            return render(request, "voting/vote.html", {
                "election": election,
                "form": form,
            })

        candidate = form.cleaned_data["candidate"]

        if candidate.election != election:
            log_action(request, "INVALID_CANDIDATE", f"User {request.user} submitted invalid candidate in election {pk}")
            messages.error(request, "Invalid candidate selection.")
            return redirect("vote", pk=pk)

        Vote.objects.create(
            election=election,
            voter=request.user,
            candidate=candidate,
        )
        log_action(request, "VOTE_CAST", f"Vote cast in election {pk} for candidate {candidate.name}")
        messages.success(request, "Your vote has been recorded!")
        return redirect("vote_confirmation", pk=pk)


class VoteConfirmationView(VoterRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        return render(request, "voting/confirmation.html", {"election": election})