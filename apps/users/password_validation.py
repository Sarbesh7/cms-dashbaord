import re
from django.core.exceptions import ValidationError


class PasswordComplexityValidator:
    """
    Enforces password complexity:
    1. Minimum length (default 8).
    2. At least one uppercase English letter (A-Z).
    3. At least one number (0-9).
    4. At least one special / non-alphanumeric character.
    """

    def __init__(self, min_length=8):
        self.min_length = int(min_length)

    def validate(self, password, user=None):
        errors = []
        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    f"Password must be at least {self.min_length} characters long.",
                    code="password_too_short",
                )
            )
        if not re.search(r"[A-Z]", password):
            errors.append(
                ValidationError(
                    "Password must contain at least one uppercase letter.",
                    code="password_no_upper",
                )
            )
        if not re.search(r"[0-9]", password):
            errors.append(
                ValidationError(
                    "Password must contain at least one number.",
                    code="password_no_number",
                )
            )
        if not re.search(r"[^A-Za-z0-9]", password):
            errors.append(
                ValidationError(
                    "Password must contain at least one special character.",
                    code="password_no_special",
                )
            )
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            f"Your password must be at least {self.min_length} characters long and "
            "contain at least one uppercase letter, one number, and one special character."
        )
