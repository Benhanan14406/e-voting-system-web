import uuid
from django.db import models
from django.conf import settings

STATUS_ENUM = ["Pending", "Open", "Closed"]

class Election(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=[(status, status) for status in STATUS_ENUM], default="Pending")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)


class Candidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="candidates")
    name = models.CharField(max_length=100)
    vision = models.TextField(blank=True)
    mission = models.TextField(blank=True)

    def __str__(self):
        return self.name