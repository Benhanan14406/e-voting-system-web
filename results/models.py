import uuid
from django.db import models
from django.core.exceptions import ValidationError
from elections.models import Election, Candidate
from voting.models import Vote

class Result(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    total_votes = models.PositiveIntegerField(default=0)

    def calculate_result(self) -> dict:
        candidates = Candidate.objects.filter(election=self.election)
        votes = Vote.objects.filter(election=self.election)

        counted_votes = 0
        candidate_votes = {candidate: 0 for candidate in candidates}
        for candidate in candidates:
            candidate_votes[candidate] = votes.filter(candidate=candidate).count()
            counted_votes += candidate_votes[candidate]

        if self.total_votes != counted_votes:
            raise ValidationError("Total votes do not match counted votes")

        return candidate_votes