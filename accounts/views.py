from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, LoginAttempt, MFASecret
from .forms import LoginForm, RegisterForm, MFASetupConfirmForm, MFAVerifyForm
from .mfa_utils import generate_totp_secret, verify_totp, generate_qr_code_base64
from audit.utils import log_action

MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0]
    return request.META.get("REMOTE_ADDR")

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
        log_action(request, "REGISTRATION_SUCCESSFUL", f"User {user.username} registered successfully.")
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

        cutoff = timezone.now() - timedelta(minutes=LOCKOUT_MINUTES)
        recent_failures = LoginAttempt.objects.filter(username=username, success=False, attempted_at__gte=cutoff).count()
        if recent_failures >= MAX_ATTEMPTS:
            messages.error(request, f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.")
            log_action(request, "LOGIN_FAILED", f"User {username} locked out due to too many failed attempts.")
            
            return render(request, "accounts/login.html", {"form": form})

        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            LoginAttempt.objects.create(username=username, ip_address=ip, success=True)
            
            try:
                mfa = user.mfa_secret
                if mfa.enabled:
                    request.session.cycle_key()
                    request.session["mfa_user_id"] = str(user.pk)
                    log_action(request, "LOGIN_MFA_REQUIRED", f"User {username} passed password, awaiting MFA.")
                    return redirect("mfa_verify")
            except MFASecret.DoesNotExist:
                pass
            
            request.session.cycle_key()
            login(request, user)
            log_action(request, "LOGIN_SUCCESSFUL", f"User {username} logged in successfully.")
            return redirect("dashboard")
        else:
            LoginAttempt.objects.create(username=username, ip_address=ip, success=False)
            log_action(request, "LOGIN_FAILED", f"User {username} failed to log in.")
            messages.error(request, "Invalid username or password.")
            return render(request, "accounts/login.html", {"form": form})

class Logout(View):
    def post(self, request, *args, **kwargs):
        log_action(request, "LOGOUT", f"User {request.user.username} logged out.")
        logout(request)
        return redirect("login")
    
class MFAVerifyView(View):
    def get(self, request):
        if "mfa_user_id" not in request.session:
            return redirect("login")
        return render(request, "accounts/mfa_verify.html", {"form": MFAVerifyForm()})
 
    def post(self, request):
        if "mfa_user_id" not in request.session:
            return redirect("login")
 
        form = MFAVerifyForm(request.POST)
        if not form.is_valid():
            return render(request, "accounts/mfa_verify.html", {"form": form})
 
        code = form.cleaned_data["code"]
        user_id = request.session.get("mfa_user_id")
 
        try:
            user = CustomUser.objects.get(pk=user_id)
            mfa = user.mfa_secret
        except (CustomUser.DoesNotExist, MFASecret.DoesNotExist):
            messages.error(request, "Session expired. Please log in again.")
            return redirect("login")
 
        if verify_totp(mfa.secret, code):
            del request.session["mfa_user_id"]
            request.session.cycle_key()
            login(request, user)
            log_action(request, "LOGIN_MFA_SUCCESS", f"User {user.username} completed MFA successfully.")
            return redirect("dashboard")
        else:
            log_action(request, "LOGIN_MFA_FAILED", f"User {user.username} entered wrong MFA code.")
            messages.error(request, "Invalid verification code. Please try again.")
            return render(request, "accounts/mfa_verify.html", {"form": MFAVerifyForm()})
 
 
class MFASetupView(LoginRequiredMixin, View):
    def get(self, request):
        secret = generate_totp_secret()
        request.session["mfa_pending_secret"] = secret
        qr_code = generate_qr_code_base64(secret, request.user.username)
        return render(request, "accounts/mfa_setup.html", {"qr_code": qr_code, "secret": secret, "form": MFASetupConfirmForm()})
 
    def post(self, request):
        form = MFASetupConfirmForm(request.POST)
        if not form.is_valid():
            secret = request.session.get("mfa_pending_secret", generate_totp_secret())
            request.session["mfa_pending_secret"] = secret
            qr_code = generate_qr_code_base64(secret, request.user.username)
            return render(request, "accounts/mfa_setup.html", {"qr_code": qr_code, "secret": secret, "form": form})
 
        code = form.cleaned_data["code"]
        secret = request.session.get("mfa_pending_secret")
        if not secret:
            messages.error(request, "Setup session expired. Please try again.")
            return redirect("mfa_setup")
 
        if not verify_totp(secret, code):
            messages.error(request, "Invalid code. Make sure your authenticator app is set up correctly.")
            qr_code = generate_qr_code_base64(secret, request.user.username)
            return render(request, "accounts/mfa_setup.html", {"qr_code": qr_code, "secret": secret, "form": MFASetupConfirmForm()})
 
        MFASecret.objects.update_or_create(user=request.user, defaults={"secret": secret, "enabled": True},)
        del request.session["mfa_pending_secret"]
 
        log_action(request, "MFA_ENABLED", f"User {request.user.username} enabled MFA.")
        messages.success(request, "Two-factor authentication has been enabled on your account.")
        return redirect("dashboard")
 
 
class MFADisableView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "accounts/mfa_disable.html", {"form": MFAVerifyForm()})
 
    def post(self, request):
        form = MFAVerifyForm(request.POST)
        if not form.is_valid():
            return render(request, "accounts/mfa_disable.html", {"form": form})
 
        code = form.cleaned_data["code"]
 
        try:
            mfa = request.user.mfa_secret
        except MFASecret.DoesNotExist:
            messages.info(request, "MFA is not enabled on your account.")
            return redirect("dashboard")
 
        if verify_totp(mfa.secret, code):
            mfa.delete()
            log_action(request, "MFA_DISABLED", f"User {request.user.username} disabled MFA.")
            messages.success(request, "Two-factor authentication has been disabled.")
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid code.")
            return render(request, "accounts/mfa_disable.html", {"form": MFAVerifyForm()})