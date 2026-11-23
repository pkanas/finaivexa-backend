from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.categories.models import Category
from apps.common.models import TimeStampedModel


class Budget(TimeStampedModel):
    """A monthly spending limit, either overall (category=None) or per category."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="budgets",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.PositiveIntegerField()
    alert_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("80.00"),
        validators=[MinValueValidator(Decimal(0)), MaxValueValidator(Decimal(100))],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-year", "-month", "category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "month", "year"],
                name="uniq_budget_scope",
            )
        ]
        indexes = [models.Index(fields=["user", "year", "month"])]

    def __str__(self):
        scope = self.category.name if self.category else "Overall"
        return f"{scope} {self.month:02d}/{self.year}: {self.amount}"
