import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class CustomPasswordValidator:
    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError(
                _("This password must contain at least 8 characters."),
                code="password_too_short",
            )
        if not any(char.isdigit() for char in password):
            raise ValidationError(
                _("This password must contain at least one digit."),
                code="password_no_digit",
            )
        if not any(char.isupper() for char in password):
            raise ValidationError(
                _("This password must contain at least one uppercase letter."),
                code="password_no_upper",
            )
        if not any(char in "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~" for char in password):
            raise ValidationError(
                _("This password must contain at least one special character."),
                code="password_no_special",
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least 8 characters, one digit, "
            "one uppercase letter, and one special character."
        )