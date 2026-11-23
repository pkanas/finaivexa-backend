"""Signal handlers that bootstrap per-user data."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, User


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    Profile.objects.get_or_create(user=instance)

    # Import lazily to avoid an app-loading cycle.
    from apps.categories.services import CategoryService

    CategoryService.ensure_default_categories(instance)
