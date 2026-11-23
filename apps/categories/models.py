from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    """Income/expense categories.

    ``user=None`` marks a global default category; otherwise the category is
    private to that user.
    """

    class Type(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=Type.choices, db_index=True)
    icon = models.CharField(max_length=64, blank=True, default="")
    color = models.CharField(max_length=16, blank=True, default="#6c757d")
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "type"],
                name="uniq_custom_category_per_user",
                condition=models.Q(user__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["name", "type"],
                name="uniq_default_category",
                condition=models.Q(user__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.type})"

    @property
    def scope(self):
        return "default" if self.user_id is None else "custom"
