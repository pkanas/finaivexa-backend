"""Reusable authentication services."""
from .models import User


class AuthService:
    @staticmethod
    def register(password, **fields):
        """Create a user (signals create the profile and default categories)."""
        return User.objects.create_user(password=password, **fields)
