from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from elections.models import Election
from voting.models import Vote

@login_required
def dashboard(request):
    if request.user.role == "admin":
        elections = Election.objects.all().order_by("-created_at")
        return render(request, "core/dashboard_admin.html", {"elections": elections})
    else:
        elections = Election.objects.filter(status="open")
        voted_ids = Vote.objects.filter(
            voter=request.user
        ).values_list("election_id", flat=True)
        return render(request, "core/dashboard_voter.html", {
            "elections": elections,
            "voted_ids": voted_ids,
        })