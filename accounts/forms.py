from django import forms
from django.contrib.auth.forms import UserCreationForm
from captcha.fields import CaptchaField
from .models import CustomUser
import re

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "Username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))
    captcha = CaptchaField()

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    captcha = CaptchaField()

    class Meta:
        model = CustomUser
        fields = ["username", "email", "password1", "password2"]

    def clean_username(self):
        username = self.cleaned_data["username"]
        
        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            raise forms.ValidationError("Username must be 3–30 characters, alphanumeric and underscore only.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email.lower()
    
    def clean_password(self):
        password1 = self.cleaned_data["password1"]
        password2 = self.cleaned_data["password2"]

        if password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        return password1
    
class MFAVerifyForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "placeholder": "6-digit code",
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "pattern": "[0-9]{6}",
        }),
        label="Authenticator code",
    )
 
    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Code must be 6 digits.")
        return code

class MFASetupConfirmForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "placeholder": "6-digit code from your app",
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "pattern": "[0-9]{6}",
        }),
        label="Confirm code from authenticator app",
    )
 
    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Code must be 6 digits.")
        return code
