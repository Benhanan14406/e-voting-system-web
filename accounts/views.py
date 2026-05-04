from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, LoginAttempt
from .forms import LoginForm, RegisterForm


MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def user_list():
    users = CustomUser.objects.all()
    return users

def user_detail(user_id):
    user = CustomUser.objects.get(id=user_id)
    return user 

def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        ip = get_client_ip(request)

        # Rate limiting check
        cutoff = timezone.now() - timedelta(minutes=LOCKOUT_MINUTES)
        recent_failures = LoginAttempt.objects.filter(
            username=username,
            success=False,
            attempted_at__gte=cutoff
        ).count()

        if recent_failures >= MAX_ATTEMPTS:
            messages.error(request, f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.")
            return render(request, "accounts/login.html", {"form": form})

        user = authenticate(request, username=username, password=password)

        if user and user.is_active:
            LoginAttempt.objects.create(username=username, ip_address=ip, success=True)
            login(request, user)
            return redirect("dashboard")
        else:
            LoginAttempt.objects.create(username=username, ip_address=ip, success=False)
            messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html", {"form": form})

def register_view(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.role = "Voter"
        user.save()
        messages.success(request, "Registration successful! Please log in.")
        return redirect("login")
    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0]
    return request.META.get("REMOTE_ADDR")