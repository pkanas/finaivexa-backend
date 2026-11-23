"""Aggregations that power the dashboard."""
from decimal import Decimal

from apps.budgets.services import BudgetService
from apps.common.utils import current_year_month, month_bounds, percentage, to_money
from apps.transactions.serializers import TransactionSerializer
from apps.transactions.services import TransactionService


class DashboardService:
    @staticmethod
    def summary(user):
        year, month = current_year_month()
        start, end = month_bounds(year, month)
        all_time = TransactionService.totals(user)
        this_month = TransactionService.totals(user, start, end)
        last_month_start, last_month_end = _previous_month_bounds(year, month)
        last_month = TransactionService.totals(user, last_month_start, last_month_end)

        income = all_time["total_income"]
        expenses = all_time["total_expenses"]
        savings_rate = percentage(income - expenses, income) if income else 0.0

        return {
            "total_income": income,
            "total_expenses": expenses,
            "available_balance": all_time["balance"],
            "savings_rate": savings_rate,
            "this_month": {
                "income": this_month["total_income"],
                "expenses": this_month["total_expenses"],
                "net": this_month["balance"],
                "transaction_count": this_month["transaction_count"],
                "expense_change_pct": _change_pct(
                    this_month["total_expenses"], last_month["total_expenses"]
                ),
            },
            "active_budget_alerts": len(BudgetService.alerts(user, year, month)),
        }

    @staticmethod
    def monthly_spending(user, months=12):
        return TransactionService.monthly_series(user, months=months)

    @staticmethod
    def category_spending(user, year=None, month=None):
        year = year or current_year_month()[0]
        month = month or current_year_month()[1]
        start, end = month_bounds(year, month)
        return {
            "year": year,
            "month": month,
            "categories": TransactionService.category_breakdown(
                user, start, end, category_type="expense"
            ),
        }

    @staticmethod
    def recent_transactions(user, limit=5):
        qs = TransactionService.for_user(user)[:limit]
        request = None
        return TransactionSerializer(qs, many=True, context={"request": request}).data


def _previous_month_bounds(year, month):
    from apps.common.utils import shift_month

    py, pm = shift_month(year, month, -1)
    return month_bounds(py, pm)


def _change_pct(current, previous):
    previous = Decimal(str(previous or 0))
    if previous == 0:
        return 0.0
    return float(((Decimal(str(current or 0)) - previous) / previous * 100).quantize(Decimal("0.01")))
