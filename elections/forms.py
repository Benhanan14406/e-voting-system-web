from django import forms
from .models import Election, Candidate
import bleach

ALLOWED_TAGS = []

def sanitize(value):
    return bleach.clean(value, tags=ALLOWED_TAGS, strip=True)

class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ["title", "description", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_title(self):
        return sanitize(self.cleaned_data["title"])

    def clean_description(self):
        return sanitize(self.cleaned_data["description"])

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        if start and end and end <= start:
            raise forms.ValidationError("End date must be after start date.")
        return cleaned_data


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ["name", "vision", "mission"]

    def clean_name(self):
        return sanitize(self.cleaned_data["name"])

    def clean_vision(self):
        return sanitize(self.cleaned_data["vision"])

    def clean_mission(self):
        return sanitize(self.cleaned_data["mission"])