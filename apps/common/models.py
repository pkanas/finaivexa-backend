"""Reusable abstract models."""
from django.db import models


class TimeStampedModel(models.Model):
    """Adds self-managed created/updated timestamps to a model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
