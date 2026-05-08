from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from accounts.models import CustomUser
from .models import AuditLog
from .utils import log_action

class AuditLogModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="audituser",
            password="Testpass1",
            email="audit@test.com",
            role="Admin"
        )

    def test_audit_log_created(self):
        AuditLog.objects.create(
            user=self.user,
            action="TEST_ACTION",
            details="test details",
            ip_address="127.0.0.1",
            integrity_hash="a" * 64
        )
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_audit_log_cannot_be_deleted(self):
        log = AuditLog.objects.create(
            user=self.user,
            action="TEST_ACTION",
            details="test",
            ip_address="127.0.0.1",
            integrity_hash="a" * 64
        )
        with self.assertRaises(PermissionDenied):
            log.delete()

    def test_audit_log_queryset_cannot_be_deleted(self):
        AuditLog.objects.create(
            user=self.user,
            action="TEST_ACTION",
            details="test",
            ip_address="127.0.0.1",
            integrity_hash="a" * 64
        )
        with self.assertRaises(PermissionDenied):
            AuditLog.objects.all().delete()

    def test_integrity_hash_is_sha256(self):
        import hashlib
        log = AuditLog.objects.create(
            user=self.user,
            action="TEST_ACTION",
            details="test",
            ip_address="127.0.0.1",
            integrity_hash="a" * 64
        )
        # SHA-256 produces 64 hex chars
        self.assertEqual(len(log.integrity_hash), 64)

    def test_ordering_is_newest_first(self):
        AuditLog.objects.create(user=self.user, action="FIRST", ip_address="127.0.0.1", integrity_hash="a" * 64)
        AuditLog.objects.create(user=self.user, action="SECOND", ip_address="127.0.0.1", integrity_hash="b" * 64)
        logs = AuditLog.objects.all()
        self.assertEqual(logs[0].action, "SECOND")


class AuditLogViewTest(TestCase):
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

    def test_admin_can_view_audit_log(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("audit_log"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "audit/log.html")

    def test_voter_cannot_view_audit_log(self):
        self.client.force_login(self.voter)
        response = self.client.get(reverse("audit_log"))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_cannot_view_audit_log(self):
        response = self.client.get(reverse("audit_log"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('audit_log')}")