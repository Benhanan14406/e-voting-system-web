from django import forms
from elections.models import Candidate

class VoteForm(forms.Form):
    candidate = forms.ModelChoiceField(
        queryset=Candidate.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
    )

    def __init__(self, *args, **kwargs):
        election = kwargs.pop("election")
        super().__init__(*args, **kwargs)
        self.fields["candidate"].queryset = Candidate.objects.filter(election=election)