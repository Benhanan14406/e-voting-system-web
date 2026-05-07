from django.urls import path
from .views import Register, Login, Logout, MFASetupView, MFAVerifyView, MFADisableView

urlpatterns = [
    path("register/", Register.as_view(), name="register"),
    path("login/", Login.as_view(), name="login"),
    path("logout/", Logout.as_view(), name="logout"),
    path("mfa/verify/", MFAVerifyView.as_view(), name="mfa_verify"),
    path("mfa/setup/", MFASetupView.as_view(), name="mfa_setup"),
    path("mfa/disable/", MFADisableView.as_view(), name="mfa_disable"),
]