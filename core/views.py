from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from elections.models import Election
from voting.models import Vote, generate_voter_token

@login_required
def dashboard(request):
    if request.user.role == "Admin":
        elections = Election.objects.all().order_by("-created_at")
        return render(request, "core/dashboard_admin.html", {"elections": elections})
    else:
        elections = Election.objects.filter(status="Open")
        voted_ids = [
            e.pk for e in elections
            if Vote.objects.filter(
                election=e,
                voter_token=generate_voter_token(request.user.id, e.pk)
            ).exists()
        ]

        return render(request, "core/dashboard_voter.html", {
            "elections": elections,
            "voted_ids": voted_ids,
        })