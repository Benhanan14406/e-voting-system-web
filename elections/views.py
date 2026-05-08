from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.contrib import messages
from .models import Election, Candidate
from .forms import ElectionForm, CandidateForm
from audit.utils import log_action
from voting.models import Vote
from results.models import Result

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_admin()


class ElectionListView(AdminRequiredMixin, View):
    def get(self, request):
        elections = Election.objects.all().order_by("-created_at")
        return render(request, "elections/list.html", {"elections": elections})


class ElectionCreateView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, "elections/form.html", {"form": ElectionForm(), "action": "Create"})

    def post(self, request):
        form = ElectionForm(request.POST)
        if not form.is_valid():
            return render(request, "elections/form.html", {"form": form, "action": "Create"})
        election = form.save(commit=False)
        election.created_by = request.user
        election.save()

        log_action(request, "ELECTION_CREATE", f"Election created: {election.title}")
        messages.success(request, "Election created successfully.")

        return redirect("election_list")


class ElectionOpenView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != "Pending":
            messages.error(request, "Only pending elections can be opened!")
            return redirect("election_list")
        
        election.status = "Open"
        election.save()

        log_action(request, "ELECTION_OPEN", f"Election \"{election.title}\" opened")
        messages.success(request, f"\"{election.title}\" is now open.")

        return redirect("election_list")


class ElectionCloseView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != "Open":
            messages.error(request, "Only open elections can be closed!")
            return redirect("election_list")
        
        election.status = "Closed"
        election.save()

        total_votes = Vote.objects.filter(election=election).count()
        result = Result.objects.create(election=election, total_votes=total_votes)
        result.save()

        log_action(request, "ELECTION_CLOSE", f"Election \"{election.title}\" closed. Result {result.id} created with total votes = {total_votes}.")
        messages.success(request, f"\"{election.title}\" has been closed.")

        return redirect("election_list")


class CandidateListView(AdminRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        candidates = election.candidates.all()
        form = CandidateForm()

        return render(request, "elections/candidates.html", {"election": election, "candidates": candidates, "form": form,})


class CandidateCreateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != "Pending":
            messages.error(request, "Candidates can only be added to pending elections!")
            return redirect("candidate_list", pk=pk)
        
        form = CandidateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid input.")
            return redirect("candidate_list", pk=pk)
        
        candidate = form.save(commit=False)
        candidate.election = election
        candidate.save()

        log_action(request, "CANDIDATE_ADD", f"Candidate \"{candidate.name}\" added to \"{election.title}\"")
        messages.success(request, f"Candidate \"{candidate.name}\" added.")

        return redirect("candidate_list", pk=pk)


class CandidateDeleteView(AdminRequiredMixin, View):
    def post(self, request, pk):
        candidate = get_object_or_404(Candidate, pk=pk)
        election_pk = candidate.election.pk
        if candidate.election.status != "Pending":
            messages.error(request, "Candidates cannot be removed once the election is open!")
            return redirect("candidate_list", pk=election_pk)
        
        log_action(request, "CANDIDATE_DELETE", f"Candidate \"{candidate.name}\" deleted")
        candidate.delete()
        messages.success(request, "Candidate removed.")

        return redirect("candidate_list", pk=election_pk)