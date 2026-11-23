from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.categories.models import Category
from apps.common.models import TimeStampedModel


class Group(TimeStampedModel):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    currency = models.CharField(max_length=3, default="USD")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="groups_created",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="GroupMember",
        related_name="finance_groups",
    )

    def __str__(self):
        return self.name

    def is_member(self, user) -> bool:
        return self.members.filter(pk=user.pk).exists()

    def is_admin(self, user) -> bool:
        return self.memberships.filter(user=user, role=GroupMember.Role.ADMIN).exists()


class GroupMember(TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="uniq_group_member")
        ]

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"


class GroupExpense(TimeStampedModel):
    class SplitType(models.TextChoices):
        EQUAL = "equal", "Equal"
        CUSTOM = "custom", "Custom amounts"
        PERCENTAGE = "percentage", "Percentages"

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="expenses")
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_expenses_paid",
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    date = models.DateField(default=timezone.localdate)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    split_type = models.CharField(max_length=10, choices=SplitType.choices, default=SplitType.EQUAL)

    def __str__(self):
        return f"{self.description} ({self.amount})"


class ExpenseShare(models.Model):
    expense = models.ForeignKey(GroupExpense, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expense_shares"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_settled = models.BooleanField(default=False)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["expense", "user"], name="uniq_expense_share")
        ]

    def __str__(self):
        return f"{self.user.email} owes {self.amount} for {self.expense.description}"


class Settlement(TimeStampedModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="settlements")
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settlements_paid"
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settlements_received"
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    note = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.from_user.email} -> {self.to_user.email}: {self.amount}"
