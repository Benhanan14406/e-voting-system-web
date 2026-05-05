from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.db.models import Count
from elections.models import Election, Candidate
from voting.models import Vote
from audit.utils import log_action


class ResultsView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)

        if election.status != "closed" and request.user.role != "admin":
            messages.warning(request, "Results are only available after the election closes.")
            return redirect("dashboard")

        results = Candidate.objects.filter(election=election).annotate(
            vote_count=Count("vote")
        ).order_by("-vote_count")

        total_votes = Vote.objects.filter(election=election).count()

        log_action(request, "RESULTS_VIEW", f"Election \"{election.title}\" results viewed by {request.user}")

        return render(request, "results/results.html", {
            "election": election,
            "results": results,
            "total_votes": total_votes,
        })