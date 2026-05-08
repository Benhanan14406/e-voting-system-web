from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election, Candidate
from .models import Vote, generate_voter_token

class VoteModelTest(TestCase):
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
            status="Open",
            created_by=self.admin
        )
        self.candidate = Candidate.objects.create(
            election=self.election,
            name="Candidate A",
            vision="Vision",
            mission="Mission"
        )

    def test_generate_voter_token_is_deterministic(self):
        token1 = generate_voter_token(self.voter.id, self.election.id)
        token2 = generate_voter_token(self.voter.id, self.election.id)
        self.assertEqual(token1, token2)

    def test_different_voters_get_different_tokens(self):
        voter2 = CustomUser.objects.create_user(
            username="voter2",
            password="Testpass1",
            email="voter2@test.com",
            role="Voter"
        )
        token1 = generate_voter_token(self.voter.id, self.election.id)
        token2 = generate_voter_token(voter2.id, self.election.id)
        self.assertNotEqual(token1, token2)

    def test_vote_is_unique_per_election(self):
        token = generate_voter_token(self.voter.id, self.election.id)
        Vote.objects.create(
            election=self.election,
            voter_token=token,
            candidate=self.candidate
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Vote.objects.create(
                election=self.election,
                voter_token=token,
                candidate=self.candidate
            )


class CastVoteViewTest(TestCase):
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
        self.election = Election.objects.create(
            title="Test Election",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Open",
            created_by=self.admin
        )
        self.candidate = Candidate.objects.create(
            election=self.election,
            name="Candidate A",
            vision="Vision",
            mission="Mission"
        )

    def test_voter_can_access_vote_page(self):
        self.client.force_login(self.voter)
        response = self.client.get(reverse("vote", kwargs={"pk": self.election.pk}))
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_access_vote_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("vote", kwargs={"pk": self.election.pk}))
        self.assertEqual(response.status_code, 403)

    def test_voter_can_cast_vote(self):
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse("vote", kwargs={"pk": self.election.pk}),
            {"candidate": str(self.candidate.pk)}
        )
        token = generate_voter_token(self.voter.id, self.election.id)
        self.assertTrue(Vote.objects.filter(election=self.election, voter_token=token).exists())

    def test_voter_cannot_vote_twice(self):
        self.client.force_login(self.voter)
        self.client.post(
            reverse("vote", kwargs={"pk": self.election.pk}),
            {"candidate": str(self.candidate.pk)}
        )
        # Second vote attempt
        response = self.client.post(
            reverse("vote", kwargs={"pk": self.election.pk}),
            {"candidate": str(self.candidate.pk)}
        )
        self.assertEqual(Vote.objects.filter(election=self.election).count(), 1)
        self.assertRedirects(response, reverse("dashboard"))

    def test_cannot_vote_on_closed_election(self):
        self.election.status = "Closed"
        self.election.save()
        self.client.force_login(self.voter)
        response = self.client.get(reverse("vote", kwargs={"pk": self.election.pk}))
        self.assertEqual(response.status_code, 404)

    def test_cannot_vote_on_pending_election(self):
        self.election.status = "Pending"
        self.election.save()
        self.client.force_login(self.voter)
        response = self.client.get(reverse("vote", kwargs={"pk": self.election.pk}))
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_cannot_vote(self):
        response = self.client.get(reverse("vote", kwargs={"pk": self.election.pk}))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('vote', kwargs={'pk': self.election.pk})}"
        )

    def test_vote_is_locked(self):
        self.client.force_login(self.voter)
        self.client.post(
            reverse("vote", kwargs={"pk": self.election.pk}),
            {"candidate": str(self.candidate.pk)}
        )
        token = generate_voter_token(self.voter.id, self.election.id)
        vote = Vote.objects.get(election=self.election, voter_token=token)
        self.assertTrue(vote.is_locked)