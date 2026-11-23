from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.categories.models import Category
from apps.common.models import TimeStampedModel


class Transaction(TimeStampedModel):
    class Type(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI = "ai", "AI Categorized"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
        db_index=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="transactions",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=10, choices=Type.choices, db_index=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    description = models.CharField(max_length=255)
    date = models.DateField(default=timezone.localdate, db_index=True)
    payment_method = models.CharField(max_length=50, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    is_recurring = models.BooleanField(default=False)
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANUAL
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["user", "type"]),
            models.Index(fields=["user", "category"]),
        ]

    def __str__(self):
        return f"{self.description} - {self.amount}"
