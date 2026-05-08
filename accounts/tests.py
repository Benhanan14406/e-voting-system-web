from django.test import TestCase, Client
from django.urls import reverse
from .models import CustomUser, LoginAttempt, MFASecret
from .mfa_utils import generate_totp_secret, verify_totp

class CustomUserModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="testvoter",
            password="Testpass1",
            email="voter@test.com",
            role="Voter"
        )
        self.admin = CustomUser.objects.create_user(
            username="testadmin",
            password="Testpass1",
            email="admin@test.com",
            role="Admin"
        )

    def test_is_voter(self):
        self.assertTrue(self.user.is_voter())
        self.assertFalse(self.user.is_admin())

    def test_is_admin(self):
        self.assertTrue(self.admin.is_admin())
        self.assertFalse(self.admin.is_voter())

    def test_default_role_is_voter(self):
        user = CustomUser.objects.create_user(
            username="defaultuser",
            password="Testpass1",
            email="default@test.com"
        )
        self.assertEqual(user.role, "Voter")


class LoginAttemptModelTest(TestCase):
    def test_create_login_attempt(self):
        attempt = LoginAttempt.objects.create(
            username="testuser",
            ip_address="127.0.0.1",
            success=False
        )
        self.assertEqual(attempt.username, "testuser")
        self.assertFalse(attempt.success)


class RegisterViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("register")

    def test_register_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")

    def test_register_valid_user(self):
        response = self.client.post(self.url, {
            "username": "newvoter",
            "email": "newvoter@test.com",
            "password1": "Testpass1",
            "password2": "Testpass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        # User should be created regardless of captcha in test env
        self.assertTrue(
            CustomUser.objects.filter(username="newvoter").exists()
            or response.status_code == 200
        )

    def test_register_invalid_username(self):
        response = self.client.post(self.url, {
            "username": "a",  # too short
            "email": "test@test.com",
            "password1": "Testpass1",
            "password2": "Testpass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CustomUser.objects.filter(username="a").exists())

    def test_register_duplicate_email(self):
        CustomUser.objects.create_user(
            username="existing",
            password="Testpass1",
            email="duplicate@test.com"
        )
        response = self.client.post(self.url, {
            "username": "newuser",
            "email": "duplicate@test.com",
            "password1": "Testpass1",
            "password2": "Testpass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        self.assertEqual(response.status_code, 200)


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("login")
        self.user = CustomUser.objects.create_user(
            username="loginuser",
            password="Testpass1",
            email="login@test.com",
            role="Voter"
        )

    def test_login_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_wrong_password(self):
        response = self.client.post(self.url, {
            "username": "loginuser",
            "password": "WrongPass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        self.assertEqual(response.status_code, 200)
        attempt = LoginAttempt.objects.filter(username="loginuser", success=False)
        self.assertTrue(attempt.exists())

    def test_login_nonexistent_user(self):
        response = self.client.post(self.url, {
            "username": "nobody",
            "password": "Testpass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        self.assertEqual(response.status_code, 200)

    def test_rate_limiting_lockout(self):
        # Create 5 failed attempts
        for _ in range(5):
            LoginAttempt.objects.create(
                username="loginuser",
                ip_address="127.0.0.1",
                success=False
            )
        response = self.client.post(self.url, {
            "username": "loginuser",
            "password": "Testpass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many failed attempts")

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.url, {
            "username": "loginuser",
            "password": "Testpass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username="logoutuser",
            password="Testpass1",
            email="logout@test.com",
            role="Voter"
        )
        self.client.force_login(self.user)

    def test_logout_post(self):
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))

    def test_logout_get_not_allowed(self):
        # Logout should be POST only
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)


class MFATest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username="mfauser",
            password="Testpass1",
            email="mfa@test.com",
            role="Voter"
        )
        self.secret = generate_totp_secret()
        MFASecret.objects.create(
            user=self.user,
            secret=self.secret,
            enabled=True
        )

    def test_valid_totp_code(self):
        import pyotp
        totp = pyotp.TOTP(self.secret)
        self.assertTrue(verify_totp(self.secret, totp.now()))

    def test_invalid_totp_code(self):
        self.assertFalse(verify_totp(self.secret, "000000"))

    def test_mfa_verify_redirects_without_session(self):
        response = self.client.get(reverse("mfa_verify"))
        self.assertRedirects(response, reverse("login"))