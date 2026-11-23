"""Transaction queries and aggregations (all via the Django ORM)."""
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.common.utils import (
    current_year_month,
    month_bounds,
    month_label,
    percentage,
    shift_month,
    to_money,
)

from .models import Transaction


class TransactionService:
    @staticmethod
    def for_user(user):
        return Transaction.objects.filter(user=user).select_related("category")

    @classmethod
    def totals(cls, user, start_date=None, end_date=None):
        """Totals for a period (or all time when no bounds are given)."""
        qs = cls.for_user(user)
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)

        income = qs.filter(type=Transaction.Type.INCOME).aggregate(t=Sum("amount"))["t"] or Decimal(0)
        expenses = qs.filter(type=Transaction.Type.EXPENSE).aggregate(t=Sum("amount"))["t"] or Decimal(0)

        return {
            "total_income": to_money(income),
            "total_expenses": to_money(expenses),
            "balance": to_money(income - expenses),
            "transaction_count": qs.count(),
        }

    @classmethod
    def monthly_series(cls, user, months=12):
        """Income/expense totals for the last ``months`` calendar months."""
        year, month = current_year_month()
        series = []
        for offset in range(months - 1, -1, -1):
            y, m = shift_month(year, month, -offset)
            start, end = month_bounds(y, m)
            totals = cls.totals(user, start, end)
            series.append(
                {
                    "month": month_label(y, m),
                    "label": date(y, m, 1).strftime("%b %Y"),
                    "income": totals["total_income"],
                    "expenses": totals["total_expenses"],
                    "net": totals["balance"],
                }
            )
        return series

    @classmethod
    def category_breakdown(cls, user, start_date=None, end_date=None, category_type=None):
        """Per-category totals with share percentages."""
        category_type = category_type or Transaction.Type.EXPENSE
        qs = cls.for_user(user).filter(type=category_type)
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)

        rows = (
            qs.values("category_id", "category__name")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")
        )
        grand_total = sum((row["total"] or Decimal(0) for row in rows), Decimal(0))
        return [
            {
                "category_id": row["category_id"],
                "category": row["category__name"] or "Uncategorized",
                "total": to_money(row["total"]),
                "transaction_count": row["count"],
                "percentage": percentage(row["total"], grand_total),
            }
            for row in rows
        ]

    @classmethod
    def daily_series(cls, user, year, month):
        """Per-day income/expense totals for one calendar month."""
        from calendar import monthrange

        totals_by_day = {
            row["date"]: (row["income"], row["expenses"])
            for row in (
                cls.for_user(user)
                .filter(date__year=year, date__month=month)
                .values("date")
                .annotate(
                    income=Sum("amount", filter=Q(type=Transaction.Type.INCOME)),
                    expenses=Sum("amount", filter=Q(type=Transaction.Type.EXPENSE)),
                )
            )
        }

        days = []
        running = Decimal(0)
        for day in range(1, monthrange(year, month)[1] + 1):
            current = date(year, month, day)
            income, expenses = totals_by_day.get(current, (None, None))
            income = income or Decimal(0)
            expenses = expenses or Decimal(0)
            running += income - expenses
            days.append(
                {
                    "day": day,
                    "date": current.isoformat(),
                    "income": to_money(income),
                    "expenses": to_money(expenses),
                    "balance": to_money(running),
                }
            )
        return days
