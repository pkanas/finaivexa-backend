from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel

from .managers import UserManager


class User(AbstractUser):
    """Email-based user (no username) used across the whole application."""

    username = None
    email = models.EmailField(_("email address"), unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, default="")
    currency = models.CharField(max_length=3, default="USD")
    timezone = models.CharField(max_length=64, default="UTC")
    is_verified = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def display_name(self) -> str:
        return (self.get_full_name() or self.email).strip()


class Profile(TimeStampedModel):
    """Optional extended information for a user."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )
    bio = models.TextField(blank=True, default="")
    avatar_url = models.URLField(blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return f"Profile for {self.user.email}"
