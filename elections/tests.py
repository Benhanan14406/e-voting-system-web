from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from .models import Election, Candidate

class ElectionModelTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="adminuser",
            password="Testpass1",
            email="admin@test.com",
            role="Admin"
        )
        self.election = Election.objects.create(
            title="Test Election",
            description="Test",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Pending",
            created_by=self.admin
        )

    def test_election_default_status_is_pending(self):
        self.assertEqual(self.election.status, "Pending")

    def test_candidate_belongs_to_election(self):
        candidate = Candidate.objects.create(
            election=self.election,
            name="Test Candidate",
            vision="Vision",
            mission="Mission"
        )
        self.assertEqual(candidate.election, self.election)

    def test_candidates_deleted_with_election(self):
        Candidate.objects.create(
            election=self.election,
            name="Test Candidate",
            vision="Vision",
            mission="Mission"
        )
        self.election.delete()
        self.assertEqual(Candidate.objects.count(), 0)


class ElectionViewTest(TestCase):
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
            description="Test",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            status="Pending",
            created_by=self.admin
        )

    def test_voter_cannot_access_election_list(self):
        self.client.force_login(self.voter)
        response = self.client.get(reverse("election_list"))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_access_election_list(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("election_list"))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_create_election(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("election_create"), {
            "title": "New Election",
            "description": "Description",
            "start_date": "2026-01-01T00:00",
            "end_date": "2026-12-31T00:00",
        })
        self.assertTrue(Election.objects.filter(title="New Election").exists())

    def test_voter_cannot_create_election(self):
        self.client.force_login(self.voter)
        response = self.client.post(reverse("election_create"), {
            "title": "Hacked Election",
            "description": "Description",
            "start_date": "2026-01-01T00:00",
            "end_date": "2026-12-31T00:00",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Election.objects.filter(title="Hacked Election").exists())

    def test_open_election(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("election_open", kwargs={"pk": self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "Open")

    def test_cannot_open_already_open_election(self):
        self.election.status = "Open"
        self.election.save()
        self.client.force_login(self.admin)
        self.client.post(reverse("election_open", kwargs={"pk": self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "Open")

    def test_close_election(self):
        self.election.status = "Open"
        self.election.save()
        self.client.force_login(self.admin)
        self.client.post(reverse("election_close", kwargs={"pk": self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "Closed")

    def test_cannot_close_pending_election(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("election_close", kwargs={"pk": self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "Pending")


class CandidateViewTest(TestCase):
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
            status="Pending",
            created_by=self.admin
        )

    def test_admin_can_add_candidate_to_pending_election(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("candidate_add", kwargs={"pk": self.election.pk}),
            {"name": "Candidate A", "vision": "Vision", "mission": "Mission"}
        )
        self.assertTrue(Candidate.objects.filter(name="Candidate A").exists())

    def test_cannot_add_candidate_to_open_election(self):
        self.election.status = "Open"
        self.election.save()
        self.client.force_login(self.admin)
        self.client.post(
            reverse("candidate_add", kwargs={"pk": self.election.pk}),
            {"name": "Late Candidate", "vision": "Vision", "mission": "Mission"}
        )
        self.assertFalse(Candidate.objects.filter(name="Late Candidate").exists())

    def test_voter_cannot_add_candidate(self):
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse("candidate_add", kwargs={"pk": self.election.pk}),
            {"name": "Hacked Candidate", "vision": "Vision", "mission": "Mission"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Candidate.objects.filter(name="Hacked Candidate").exists())

    def test_admin_can_delete_candidate_from_pending_election(self):
        candidate = Candidate.objects.create(
            election=self.election, name="To Delete", vision="V", mission="M"
        )
        self.client.force_login(self.admin)
        self.client.post(reverse("candidate_delete", kwargs={"pk": candidate.pk}))
        self.assertFalse(Candidate.objects.filter(pk=candidate.pk).exists())

    def test_cannot_delete_candidate_from_open_election(self):
        self.election.status = "Open"
        self.election.save()
        candidate = Candidate.objects.create(
            election=self.election, name="Protected", vision="V", mission="M"
        )
        self.client.force_login(self.admin)
        self.client.post(reverse("candidate_delete", kwargs={"pk": candidate.pk}))
        self.assertTrue(Candidate.objects.filter(pk=candidate.pk).exists())