from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, LoginAttempt
from .forms import LoginForm, RegisterForm
from audit.utils import log_action

MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def user_list():
    users = CustomUser.objects.all()
    return users

def user_detail(user_id):
    user = CustomUser.objects.get(id=user_id)
    return user 

def register_view(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.role = "Voter"
        user.save()
        messages.success(request, "Registration successful! Please log in.")
        log_action(request, "registration_successful", f"User {user.username} registered successfully.")
        return redirect("login")
    return render(request, "accounts/register.html", {"form": form})

class Register(View):
    def get(self, request, *args, **kwargs):
        form = RegisterForm()
        return render(request, "accounts/register.html", {"form": form})

    def post(self, request, *args, **kwargs):
        form = RegisterForm(request.POST)
        if not form.is_valid():
            return render(request, "accounts/register.html", {"form": form})

        user = form.save(commit=False)
        user.role = "Voter"
        user.save()
        messages.success(request, "Registration successful! Please log in.")
        log_action(request, "registration_successful", f"User {user.username} registered successfully.")
        return redirect("login")

class Login(View):
    def get(self, request, *args, **kwargs):
        form = LoginForm()
        return render(request, "accounts/login.html", {"form": form})
    
    def post(self, request, *args, **kwargs):
        form = LoginForm(request.POST)
        if not form.is_valid():
            return render(request, "accounts/login.html", {"form": form})

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
            log_action(request, "login_failed", f"User {username} locked out due to too many failed attempts.")
            return render(request, "accounts/login.html", {"form": form})

        user = authenticate(request, username=username, password=password)

        if user and user.is_active:
            LoginAttempt.objects.create(username=username, ip_address=ip, success=True)
            login(request, user)
            log_action(request, "login_successful", f"User {username} logged in successfully.")
            return redirect("dashboard")
        else:
            LoginAttempt.objects.create(username=username, ip_address=ip, success=False)
            log_action(request, "login_failed", f"User {username} failed to log in.")
            messages.error(request, "Invalid username or password.")
            return render(request, "accounts/login.html", {"form": form})

class Logout(View):
    def post(self, request, *args, **kwargs):
        log_action(request, "logout", f"User {request.user.username} logged out.")
        logout(request)
        return redirect("login")

def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0]
    return request.META.get("REMOTE_ADDR")