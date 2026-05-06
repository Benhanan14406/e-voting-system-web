import re
from django.core.exceptions import ValidationError

class StrongPasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', password):
            raise ValidationError("Password must contain at least one digit.")

    def get_help_text(self):
        return "Password must contain uppercase, lowercase, and a digit."