"""Small, dependency-free helpers shared by services."""
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

MONEY = Decimal("0.01")


def to_money(value) -> Decimal:
    """Quantize a numeric value to two decimals using banker-safe rounding."""
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return the inclusive-start / exclusive-end dates for a month."""
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def current_year_month() -> tuple[int, int]:
    today = timezone.localdate()
    return today.year, today.month


def shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    """Shift a (year, month) pair by ``offset`` months."""
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def parse_date(value):
    """Parse a date from a string/date/datetime, returning ``None`` on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def month_label(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def percentage(part, total) -> float:
    total = Decimal(str(total or 0))
    if total == 0:
        return 0.0
    return float((Decimal(str(part or 0)) / total * 100).quantize(MONEY))
