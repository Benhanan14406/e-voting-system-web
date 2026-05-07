import hashlib
import uuid
from django.db import models
from django.conf import settings
from elections.models import Election, Candidate

class Vote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    voter_token = models.CharField(max_length=64)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)
    is_locked = models.BooleanField(default=True)

    class Meta:
        unique_together = [("election", "voter_token")]

def generate_voter_token(voter_id: int, election_id: int) -> str:
    raw = f"{settings.SECRET_KEY}:{voter_id}:{election_id}"
    return hashlib.sha256(raw.encode()).hexdigest()