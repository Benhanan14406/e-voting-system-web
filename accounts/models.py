from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser

ROLE_ENUM = ["Admin", "Voter"]

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=10, choices=[(role, role) for role in ROLE_ENUM], default='Voter')

    def is_admin(self):
        return self.role == 'Admin'

    def is_voter(self):
        return self.role == 'Voter'
    
class LoginAttempt(models.Model):
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    attempted_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)