from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election, Candidate
from voting.models import Vote, generate_voter_token
from .models import Result

class ResultModelTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="adminuser",
            password="Testpass1",
            email="admin@test.com",
            role="Admin"
        )
        self.voter = CustomUser.objects.create_user(
            username="voteruser",
            password="Testpass1",
            email="voter@test.com",
            role="Voter"
        )
        self.election = Election.objects.create(
            title="Test Election",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Closed",
            created_by=self.admin
        )
        self.candidate_a = Candidate.objects.create(
            election=self.election, name="Candidate A", vision="V", mission="M"
        )
        self.candidate_b = Candidate.objects.create(
            election=self.election, name="Candidate B", vision="V", mission="M"
        )
        token = generate_voter_token(self.voter.id, self.election.id)
        Vote.objects.create(
            election=self.election,
            voter_token=token,
            candidate=self.candidate_a
        )
        self.result = Result.objects.create(
            election=self.election,
            total_votes=1
        )

    def test_calculate_result_returns_dict(self):
        result_dict = self.result.calculate_result()
        self.assertIsInstance(result_dict, dict)

    def test_calculate_result_counts_correctly(self):
        result_dict = self.result.calculate_result()
        self.assertEqual(result_dict[self.candidate_a], 1)
        self.assertEqual(result_dict[self.candidate_b], 0)

    def test_calculate_result_raises_on_mismatch(self):
        self.result.total_votes = 99
        self.result.save()
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.result.calculate_result()


class ResultsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = CustomUser.objects.create_user(
            username="adminuser",
            password="Testpass1",
            email="admin@test.com",
            role="Admin"
        )
        self.voter = CustomUser.objects.create_user(
            username="voteruser",
            password="Testpass1",
            email="voter@test.com",
            role="Voter"
        )
        self.open_election = Election.objects.create(
            title="Open Election",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Open",
            created_by=self.admin
        )
        self.closed_election = Election.objects.create(
            title="Closed Election",
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(days=1),
            status="Closed",
            created_by=self.admin
        )
        Result.objects.create(election=self.closed_election, total_votes=0)

    def test_voter_can_view_closed_election_results(self):
        self.client.force_login(self.voter)
        response = self.client.get(reverse("results", kwargs={"pk": self.closed_election.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/results.html")

    def test_voter_cannot_view_open_election_results(self):
        Result.objects.create(election=self.open_election, total_votes=0)
        self.client.force_login(self.voter)
        response = self.client.get(reverse("results", kwargs={"pk": self.open_election.pk}))
        self.assertRedirects(response, reverse("dashboard"))

    def test_admin_can_view_open_election_results(self):
        Result.objects.create(election=self.open_election, total_votes=0)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("results", kwargs={"pk": self.open_election.pk}))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_cannot_view_results(self):
        response = self.client.get(reverse("results", kwargs={"pk": self.closed_election.pk}))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('results', kwargs={'pk': self.closed_election.pk})}"
        )