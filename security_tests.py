from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import CustomUser, LoginAttempt
from elections.models import Election, Candidate
from voting.models import Vote, generate_voter_token



def make_admin(**kw):
    defaults = dict(username="admin", password="admin123",
                    email="admin@gmail.com", role="Admin")
    defaults.update(kw)
    return CustomUser.objects.create_user(**defaults)

def make_voter(**kw):
    defaults = dict(username="voter", password="voter123",
                    email="voter@gmail.com", role="Voter")
    defaults.update(kw)
    return CustomUser.objects.create_user(**defaults)

def make_open_election(admin):
    return Election.objects.create(
        title="Security Test Election",
        start_date=timezone.now() - timedelta(hours=1),
        end_date=timezone.now() + timedelta(days=1),
        status="Open",
        created_by=admin,
    )

def make_candidate(election, name="Candidate A"):
    return Candidate.objects.create(
        election=election, name=name, vision="V", mission="M"
    )


class SQLInjectionLoginTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("login")

    def test_sql_injection_username_does_not_authenticate(self):
        payload = "' OR '1'='1' --"
        response = self.client.post(self.url, {
            "username": payload,
            "password": "anything",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        self.assertNotEqual(response.status_code, 302,
            "SQL injection username must not trigger a redirect (login success)")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"dashboard", response.content.lower(),
            "Dashboard content must not appear after SQL injection attempt")

    def test_sql_injection_does_not_create_login_attempt_as_success(self):
        payload = "' OR '1'='1' --"
        self.client.post(self.url, {
            "username": payload,
            "password": "anything",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        success_attempts = LoginAttempt.objects.filter(
            username=payload, success=True
        )
        self.assertFalse(success_attempts.exists(),
            "SQL injection must not create a successful LoginAttempt record")


class SQLInjectionSearchTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.force_login(self.admin)

    def test_union_injection_in_election_title_field_does_not_leak_data(self):
        payload = "' UNION SELECT username, password, null FROM users --"
        response = self.client.post(reverse("election_create"), {
            "title": payload,
            "description": "test",
            "start_date": "2030-01-01T00:00",
            "end_date": "2030-12-31T00:00",
        })
        from elections.models import Election
        election = Election.objects.filter(
            title__icontains="UNION SELECT"
        ).first()
        if election:
            self.assertIn("UNION SELECT", election.title)
            self.assertNotIn("password", election.title.replace(payload, "").lower())

    def test_no_sql_error_detail_in_response(self):
        """Response must never contain raw SQL error detail."""
        payload = "' UNION SELECT username, password, null FROM users --"
        response = self.client.post(reverse("election_create"), {
            "title": payload,
            "description": "desc",
            "start_date": "2030-01-01T00:00",
            "end_date": "2030-12-31T00:00",
        })
        content = response.content.decode()
        self.assertNotIn("OperationalError", content)
        self.assertNotIn("ProgrammingError", content)
        self.assertNotIn("sqlite3", content)
        self.assertNotIn("stack trace", content.lower())



class XSSTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.force_login(self.admin)

    def _create_election_with_title(self, title):
        self.client.post(reverse("election_create"), {
            "title": title,
            "description": "desc",
            "start_date": "2030-01-01T00:00",
            "end_date": "2030-12-31T00:00",
        })
        return Election.objects.filter().order_by("-created_at").first()

    def test_script_tag_stripped_from_election_title(self):
        payload = "<script>alert('XSS')</script>"
        election = self._create_election_with_title(payload)
        self.assertIsNotNone(election)
        self.assertNotIn("<script>", election.title)
        self.assertNotIn("</script>", election.title)

    def test_img_onerror_stripped_from_election_title(self):
        payload = "<h1>Hacked</h1><img src=x onerror=alert(1)>"
        election = self._create_election_with_title(payload)
        self.assertIsNotNone(election)
        self.assertNotIn("<h1>", election.title)
        self.assertNotIn("onerror", election.title)
        self.assertNotIn("<img", election.title)

    def test_script_tag_stripped_from_candidate_name(self):
        admin = self.admin
        election = Election.objects.create(
            title="Safe Election",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Pending",
            created_by=admin,
        )
        payload = "<script>alert('XSS')</script>Candidate"
        self.client.post(
            reverse("candidate_add", kwargs={"pk": election.pk}),
            {"name": payload, "vision": "V", "mission": "M"},
        )
        candidate = Candidate.objects.filter(election=election).first()
        if candidate:
            self.assertNotIn("<script>", candidate.name)

    def test_xss_payload_not_rendered_as_html_in_list_view(self):
        payload = "<script>alert('XSS')</script>Safe Title"
        self._create_election_with_title(payload)
        response = self.client.get(reverse("election_list"))
        content = response.content.decode()
        self.assertNotIn("<script>alert", content,
            "Raw <script> tag must not appear in rendered HTML")



class TemplateInjectionTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.client.force_login(self.admin)

    def test_template_expression_not_evaluated_in_title(self):
        payload = "{{7*7}}"
        self.client.post(reverse("election_create"), {
            "title": payload,
            "description": "desc",
            "start_date": "2030-01-01T00:00",
            "end_date": "2030-12-31T00:00",
        })
        election = Election.objects.filter(title__icontains="7").first()
        if election:
            self.assertNotEqual(election.title, "49",
                "Template expression must not be evaluated")

    def test_secret_key_not_leaked_via_template_injection(self):
        from django.conf import settings
        payload = "{{config.SECRET_KEY}}"
        self.client.post(reverse("election_create"), {
            "title": payload,
            "description": "desc",
            "start_date": "2030-01-01T00:00",
            "end_date": "2030-12-31T00:00",
        })
        response = self.client.get(reverse("election_list"))
        content = response.content.decode()
        self.assertNotIn(settings.SECRET_KEY, content,
            "SECRET_KEY must never appear in any rendered response")

class PasswordStorageTest(TestCase):

    def test_password_is_hashed_in_database(self):
        raw_password = "TestPassword123"
        user = CustomUser.objects.create_user(
            username="hashtest",
            password=raw_password,
            email="hash@test.com",
        )
        user.refresh_from_db()
        self.assertNotEqual(user.password, raw_password,
            "Plaintext password must never be stored")
        self.assertTrue(
            user.password.startswith("pbkdf2_sha256$")
            or user.password.startswith("bcrypt$")
            or user.password.startswith("argon2"),
            f"Password must be a recognised hash, got: {user.password[:20]}"
        )

    def test_two_users_with_same_password_have_different_hashes(self):
        raw = "TestPassword123"
        u1 = CustomUser.objects.create_user(
            username="user1hash", password=raw, email="u1@test.com"
        )
        u2 = CustomUser.objects.create_user(
            username="user2hash", password=raw, email="u2@test.com"
        )
        self.assertNotEqual(u1.password, u2.password,
            "Same plaintext password must produce different hashes (salt)")


class BruteForceRateLimitTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse("login")
        self.user = make_voter()

    def test_lockout_after_max_failed_attempts(self):
        for i in range(5):
            LoginAttempt.objects.create(
                username=self.user.username,
                ip_address="127.0.0.1",
                success=False,
            )
        response = self.client.post(self.url, {
            "username": self.user.username,
            "password": "Testpass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many failed attempts")

    def test_correct_login_succeeds_before_lockout_threshold(self):
        for i in range(4):
            LoginAttempt.objects.create(
                username=self.user.username,
                ip_address="127.0.0.1",
                success=False,
            )
        response = self.client.post(self.url, {
            "username": self.user.username,
            "password": "Testpass1",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        content = response.content.decode()
        self.assertNotIn("Too many failed attempts", content)

    def test_wrong_password_increments_failed_attempts(self):
        before = LoginAttempt.objects.filter(
            username=self.user.username, success=False
        ).count()
        self.client.post(self.url, {
            "username": self.user.username,
            "password": "WrongPassword99",
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })
        after = LoginAttempt.objects.filter(
            username=self.user.username, success=False
        ).count()
        self.assertEqual(after, before + 1)


class SessionInvalidationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.voter = make_voter()

    def test_protected_page_inaccessible_after_logout(self):
        self.client.force_login(self.voter)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.client.post(reverse("logout"))
        response = self.client.get(reverse("dashboard"))
        self.assertNotEqual(response.status_code, 200, "Dashboard must not be accessible after logout")
        self.assertIn(response.status_code, [302, 401])

    def test_session_cookie_changes_after_logout_and_relogin(self):
        self.client.force_login(self.voter)
        old_session_key = self.client.session.session_key

        self.client.post(reverse("logout"))
        self.client.force_login(self.voter)
        new_session_key = self.client.session.session_key

        self.assertNotEqual(old_session_key, new_session_key,
            "Session key must be rotated after logout and re-login")



class BrokenAccessControlTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.election = Election.objects.create(
            title="Access Test Election",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Open",
            created_by=self.admin,
        )
        self.candidate = make_candidate(self.election)
        from results.models import Result
        self.result = Result.objects.create(
            election=Election.objects.create(
                title="Closed Election",
                start_date=timezone.now() - timedelta(days=2),
                end_date=timezone.now() - timedelta(days=1),
                status="Closed",
                created_by=self.admin,
            ),
            total_votes=0,
        )

    def _assert_requires_login(self, url):
        response = self.client.get(url)
        self.assertIn(
            response.status_code, [302, 403],
            f"Expected redirect or 403 for unauthenticated access to {url}, "
            f"got {response.status_code}"
        )
        if response.status_code == 302:
            self.assertIn("/login/", response["Location"],
                f"Redirect from {url} must point to login page")

    def test_dashboard_requires_auth(self):
        self._assert_requires_login(reverse("dashboard"))

    def test_election_list_requires_auth(self):
        self._assert_requires_login(reverse("election_list"))

    def test_election_create_requires_auth(self):
        self._assert_requires_login(reverse("election_create"))

    def test_candidate_list_requires_auth(self):
        self._assert_requires_login(
            reverse("candidate_list", kwargs={"pk": self.election.pk})
        )

    def test_vote_page_requires_auth(self):
        self._assert_requires_login(
            reverse("vote", kwargs={"pk": self.election.pk})
        )

    def test_results_requires_auth(self):
        self._assert_requires_login(
            reverse("results", kwargs={"pk": self.result.election.pk})
        )

    def test_audit_log_requires_auth(self):
        self._assert_requires_login(reverse("audit_log"))

    def test_voter_cannot_reach_election_list(self):
        voter = make_voter(username="voter_ac", email="vac@test.com")
        self.client.force_login(voter)
        response = self.client.get(reverse("election_list"))
        self.assertEqual(response.status_code, 403)

    def test_voter_cannot_reach_audit_log(self):
        voter = make_voter(username="voter_ac2", email="vac2@test.com")
        self.client.force_login(voter)
        response = self.client.get(reverse("audit_log"))
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_cast_vote(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("vote", kwargs={"pk": self.election.pk})
        )
        self.assertEqual(response.status_code, 403)



class CSRFProtectionTest(TestCase):

    def setUp(self):
        self.voter = make_voter()
        self.admin = make_admin()
        self.client = Client(enforce_csrf_checks=True) 

    def test_login_form_contains_csrf_token(self):
        client = Client() 
        response = client.get(reverse("login"))
        self.assertContains(response, "csrfmiddlewaretoken",
            msg_prefix="Login form must include csrfmiddlewaretoken hidden input")

    def test_register_form_contains_csrf_token(self):
        client = Client()
        response = client.get(reverse("register"))
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_post_with_invalid_csrf_token_returns_403(self):
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse("logout"),
            data={},
            HTTP_X_CSRFTOKEN="invalid_token_12345",
        )
        self.assertEqual(response.status_code, 403,
            "Invalid CSRF token must result in HTTP 403")

    def test_cross_origin_post_without_csrf_token_rejected(self):
        self.client.force_login(self.voter)
        election = Election.objects.create(
            title="CSRF Target Election",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Open",
            created_by=self.admin,
        )
        candidate = make_candidate(election)

        response = self.client.post(
            reverse("vote", kwargs={"pk": election.pk}),
            {"candidate": str(candidate.pk)},
            HTTP_REFERER="http://evil.example.com/csrf_attack.html",
        )
        self.assertEqual(response.status_code, 403,
            "Cross-origin POST without valid CSRF token must be rejected")
        token = generate_voter_token(self.voter.id, election.pk)
        self.assertFalse(
            Vote.objects.filter(election=election, voter_token=token).exists(),
            "Vote must not be recorded when CSRF check fails"
        )

    def test_logout_requires_post_not_get(self):
        client = Client()
        client.force_login(self.voter)
        response = client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405,
            "Logout must not be accessible via GET (method not allowed)")



class UsernameEnumerationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse("login")
        self.existing_user = make_voter()

    def _post_login(self, username, password):
        return self.client.post(self.url, {
            "username": username,
            "password": password,
            "captcha_0": "dummy",
            "captcha_1": "PASSED",
        })

    def test_wrong_password_for_existing_user_shows_generic_message(self):
        response = self._post_login(self.existing_user.username, "WrongPass999")
        self.assertContains(response, "Invalid username or password")
        self.assertNotContains(response, "Invalid password")
        self.assertNotContains(response, "Incorrect password")

    def test_nonexistent_username_shows_same_generic_message(self):
        response = self._post_login("idonotexist_xyz", "AnyPass123")
        self.assertContains(response, "Invalid username or password")
        self.assertNotContains(response, "Username not found",
            msg_prefix="Must not reveal that username does not exist")

    def test_error_messages_are_identical_for_both_scenarios(self):
        resp_wrong_pass = self._post_login(
            self.existing_user.username, "WrongPass999"
        )
        resp_no_user = self._post_login("ghost_user_xyz", "WrongPass999")

        def extract_error(response):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, "html.parser")
            msgs = [p.get_text(strip=True) for p in soup.find_all("p")
                    if "ERROR" in p.get_text()]
            return msgs

        try:
            msgs_wrong = extract_error(resp_wrong_pass)
            msgs_no_user = extract_error(resp_no_user)
            self.assertEqual(msgs_wrong, msgs_no_user,
                "Error messages for wrong-password vs non-existent-user must be identical")
        except ImportError:
            self.assertContains(resp_wrong_pass, "Invalid username or password")
            self.assertContains(resp_no_user, "Invalid username or password")


class EVotingSpecificSecurityTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_admin()
        self.voter = make_voter()
        self.voter2 = make_voter(username="voter2", email="v2@test.com")
        self.election = make_open_election(self.admin)
        self.candidate_a = make_candidate(self.election, "Candidate A")
        self.candidate_b = make_candidate(self.election, "Candidate B")

    def test_vote_form_only_accepts_valid_uuid_candidate_id(self):
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse("vote", kwargs={"pk": self.election.pk}),
            {"candidate": "1 OR 1=1"},
        )
        token = generate_voter_token(self.voter.id, self.election.pk)
        self.assertFalse(
            Vote.objects.filter(election=self.election, voter_token=token).exists(),
            "Injected candidate ID must not result in a recorded vote"
        )

    def test_xss_in_candidate_name_is_stripped(self):
        payload = "<b onmouseover=alert('voted!')>Kandidat A</b>"
        self.client.force_login(self.admin)
        pending = Election.objects.create(
            title="Pending for XSS",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Pending",
            created_by=self.admin,
        )
        self.client.post(
            reverse("candidate_add", kwargs={"pk": pending.pk}),
            {"name": payload, "vision": "V", "mission": "M"},
        )
        candidate = Candidate.objects.filter(election=pending).first()
        if candidate:
            self.assertNotIn("<b", candidate.name)
            self.assertNotIn("onmouseover", candidate.name)
            self.assertNotIn("alert", candidate.name)

    def test_voter_cannot_vote_on_behalf_of_another_voter(self):
        self.client.force_login(self.voter)
        self.client.post(
            reverse("vote", kwargs={"pk": self.election.pk}),
            {"candidate": str(self.candidate_a.pk)},
        )

        self.client.force_login(self.voter2)
        self.client.post(
            reverse("vote", kwargs={"pk": self.election.pk}),
            {"candidate": str(self.candidate_b.pk)},
        )

        token_voter = generate_voter_token(self.voter.id, self.election.pk)
        token_voter2 = generate_voter_token(self.voter2.id, self.election.pk)

        self.assertNotEqual(token_voter, token_voter2, "Two different voters must produce different tokens")

        vote1 = Vote.objects.get(election=self.election, voter_token=token_voter)
        vote2 = Vote.objects.get(election=self.election, voter_token=token_voter2)

        self.assertEqual(vote1.candidate, self.candidate_a)
        self.assertEqual(vote2.candidate, self.candidate_b)