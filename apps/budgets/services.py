"""Budget utilization and alert calculations."""
from decimal import Decimal

from django.db.models import Sum

from apps.common.utils import current_year_month, percentage, to_money
from apps.transactions.models import Transaction

from .models import Budget


class BudgetService:
    @staticmethod
    def for_user(user, year=None, month=None, active_only=False):
        qs = Budget.objects.filter(user=user).select_related("category")
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)
        if active_only:
            qs = qs.filter(is_active=True)
        return qs

    @staticmethod
    def spent(budget):
        qs = Transaction.objects.filter(
            user=budget.user,
            type=Transaction.Type.EXPENSE,
            date__year=budget.year,
            date__month=budget.month,
        )
        if budget.category_id:
            qs = qs.filter(category_id=budget.category_id)
        return to_money(qs.aggregate(total=Sum("amount"))["total"])

    @classmethod
    def utilization(cls, budget):
        spent = cls.spent(budget)
        percent = percentage(spent, budget.amount)
        remaining = to_money(Decimal(budget.amount) - spent)
        if percent > 100:
            status = "over"
        elif percent >= float(budget.alert_threshold):
            status = "warning"
        else:
            status = "safe"
        return {
            "spent": spent,
            "remaining": remaining,
            "utilization_percentage": percent,
            "status": status,
            "is_alert": percent >= float(budget.alert_threshold),
        }

    @classmethod
    def serialize(cls, budget):
        data = {
            "id": budget.id,
            "category_id": budget.category_id,
            "category": budget.category.name if budget.category else "Overall",
            "amount": to_money(budget.amount),
            "month": budget.month,
            "year": budget.year,
            "alert_threshold": budget.alert_threshold,
            "is_active": budget.is_active,
        }
        data.update(cls.utilization(budget))
        return data

    @classmethod
    def summary(cls, user, year=None, month=None):
        year = year or current_year_month()[0]
        month = month or current_year_month()[1]
        budgets = cls.for_user(user, year, month, active_only=True)
        items = [cls.serialize(budget) for budget in budgets]

        total_budget = sum((Decimal(str(i["amount"])) for i in items), Decimal(0))
        total_spent = sum((Decimal(str(i["spent"])) for i in items), Decimal(0))
        return {
            "year": year,
            "month": month,
            "total_budget": to_money(total_budget),
            "total_spent": to_money(total_spent),
            "budgets": items,
        }

    @classmethod
    def alerts(cls, user, year=None, month=None):
        return [i for i in cls.summary(user, year, month)["budgets"] if i["is_alert"]]
