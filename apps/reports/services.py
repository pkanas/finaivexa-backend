"""Reporting aggregations built exclusively on ORM queries."""
from apps.common.utils import current_year_month, month_bounds
from apps.transactions.services import TransactionService


class ReportService:
    @staticmethod
    def monthly(user, year, month):
        start, end = month_bounds(year, month)
        return {
            "period": f"{year:04d}-{month:02d}",
            "type": "monthly",
            "summary": TransactionService.totals(user, start, end),
            "categories": TransactionService.category_breakdown(user, start, end),
            "daily": TransactionService.daily_series(user, year, month),
        }

    @staticmethod
    def yearly(user, year):
        totals = TransactionService.totals(
            user,
            start_date=f"{year}-01-01",
            end_date=f"{year}-12-31",
        )
        return {
            "period": str(year),
            "type": "yearly",
            "summary": totals,
            "months": [
                {"month": f"{year:04d}-{m:02d}", **TransactionService.totals(
                    user, *month_bounds(year, m)
                )}
                for m in range(1, 13)
            ],
            "categories": TransactionService.category_breakdown(
                user, f"{year}-01-01", f"{year}-12-31"
            ),
        }

    @staticmethod
    def category(user, start_date, end_date, category_type="expense"):
        return {
            "type": "category",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "category_type": category_type,
            "summary": TransactionService.totals(user, start_date, end_date),
            "categories": TransactionService.category_breakdown(
                user, start_date, end_date, category_type=category_type
            ),
        }
