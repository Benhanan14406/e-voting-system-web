from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.db import DatabaseError
from elections.models import Election
from voting.models import Vote, generate_voter_token
import logging
import re

logger = logging.getLogger(__name__)

# Security: Maximum search query length
MAX_SEARCH_LENGTH = 200

def validate_search_query(query):
    """
    Validate search query to prevent injection attempts.
    Returns (is_valid, sanitized_query)
    """
    if not query:
        return True, ""
    
    # Check length
    if len(query) > MAX_SEARCH_LENGTH:
        logger.warning(f"Search query exceeded max length from user {request.user.id}")
        return False, ""
    
    # Check for suspicious patterns (UNION, SELECT, etc.)
    suspicious_patterns = [
        r'\bunion\b',
        r'\bselect\b',
        r'\binsert\b',
        r'\bupdate\b',
        r'\bdelete\b',
        r'\bdrop\b',
        r'\bexec\b',
        r'--',
        r'/\*',
        r'\*/',
    ]
    
    query_lower = query.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, query_lower):
            logger.warning(f"Suspicious SQL keywords detected in search query from user {request.user.username}")
            return False, ""
    
    return True, query

@login_required
def dashboard(request):
    if request.user.is_admin():
        elections = Election.objects.all().order_by("-created_at")
        return render(request, "core/dashboard_admin.html", {"elections": elections})
    else:
        elections = Election.objects.filter(status__in=["Open", "Closed"]).order_by("-created_at")
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

@login_required
def search_elections(request):
    """
    Search elections by title, status, or description.
    Protected against SQL injection via Django ORM parameterized queries
    and additional input validation.
    """
    query = request.GET.get('q', '').strip()
    elections = []
    voted_ids = []
    search_error = False
    
    try:
        # Input validation
        is_valid, clean_query = validate_search_query(query)
        
        if not is_valid:
            logger.warning(f"Invalid search query detected from user {request.user.username}")
            messages.error(request, "Invalid search query. Please try again.")
            search_error = True
            query = ""  # Reset query for display
            clean_query = ""
        
        if request.user.is_admin():
            # Admin can search all elections
            elections = Election.objects.all()
        else:
            # Voters can only search open/closed elections
            elections = Election.objects.filter(status__in=["Open", "Closed"])
        
        # Filter by search query using Django ORM (parameterized queries - SQL injection safe)
        if clean_query:
            elections = elections.filter(
                Q(title__icontains=clean_query) | 
                Q(status__icontains=clean_query) |
                Q(description__icontains=clean_query)
            )
        
        elections = elections.order_by("-created_at")
        
        # Get voted_ids for voters
        if not request.user.is_admin():
            voted_ids = [
                e.pk for e in elections
                if Vote.objects.filter(
                    election=e,
                    voter_token=generate_voter_token(request.user.id, e.pk)
                ).exists()
            ]
    
    except DatabaseError as e:
        # Catch database errors without exposing details
        logger.error(f"Database error during search for user {request.user.username}: {str(e)}")
        messages.error(request, "An error occurred while processing your search. Please try again.")
        search_error = True
    
    except Exception as e:
        # Catch unexpected errors
        logger.error(f"Unexpected error during search for user {request.user.username}: {str(e)}")
        messages.error(request, "An unexpected error occurred. Please try again.")
        search_error = True
    
    return render(request, "core/search_results.html", {
        "elections": elections,
        "query": query if not search_error else "",
        "voted_ids": voted_ids,
        "search_error": search_error,
    })