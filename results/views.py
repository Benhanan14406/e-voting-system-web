from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from elections.models import Election
from .models import Result
from audit.utils import log_action

class ResultsView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != "Closed" and request.user.role != "Admin":
            messages.warning(request, "Results are only available after the election closes.")
            return redirect("dashboard")

        result = Result.objects.get(election=election)
        results = result.calculate_result()
        total_votes = result.total_votes
        log_action(request, "RESULTS_VIEW", f"Election \"{election.title}\" results viewed by {request.user.username}")
        return render(request, "results/results.html", {"election": election, "results": results, "total_votes": total_votes,})