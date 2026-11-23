"""Category business logic, including the default category catalogue."""
from django.db.models import Q

from .models import Category

DEFAULT_EXPENSE_CATEGORIES = [
    ("Food & Dining", "utensils", "#e63946"),
    ("Groceries", "shopping-cart", "#f4a261"),
    ("Transportation", "car", "#457b9d"),
    ("Housing & Rent", "home", "#2a9d8f"),
    ("Bills & Utilities", "bolt", "#e9c46a"),
    ("Shopping", "bag", "#8e7dbe"),
    ("Entertainment", "film", "#e76f51"),
    ("Healthcare", "heartbeat", "#ef476f"),
    ("Education", "book", "#118ab2"),
    ("Travel", "plane", "#06d6a0"),
    ("Personal Care", "user", "#b56576"),
    ("Other Expense", "ellipsis", "#6c757d"),
]

DEFAULT_INCOME_CATEGORIES = [
    ("Salary", "briefcase", "#2a9d8f"),
    ("Freelance", "laptop", "#457b9d"),
    ("Investments", "chart-line", "#e9c46a"),
    ("Business", "building", "#8e7dbe"),
    ("Gifts", "gift", "#ef476f"),
    ("Other Income", "ellipsis", "#6c757d"),
]


class CategoryService:
    """Central place for category queries and default bootstrap."""

    @classmethod
    def ensure_default_categories(cls, user):
        """Idempotently create the global default catalogue."""
        for name, icon, color in DEFAULT_EXPENSE_CATEGORIES:
            Category.objects.get_or_create(
                user=None,
                name=name,
                type=Category.Type.EXPENSE,
                defaults={"icon": icon, "color": color, "is_default": True},
            )
        for name, icon, color in DEFAULT_INCOME_CATEGORIES:
            Category.objects.get_or_create(
                user=None,
                name=name,
                type=Category.Type.INCOME,
                defaults={"icon": icon, "color": color, "is_default": True},
            )

    @classmethod
    def visible_to(cls, user, category_type=None):
        """Categories a user may use: their own plus global defaults."""
        qs = Category.objects.filter(Q(user=user) | Q(user__isnull=True))
        if category_type:
            qs = qs.filter(type=category_type)
        return qs

    @classmethod
    def resolve_for_user(cls, category_id, user, expected_type=None):
        """Return a visible category or ``None``; never leaks other users' data."""
        if category_id in (None, ""):
            return None
        qs = cls.visible_to(user).filter(pk=category_id)
        if expected_type:
            qs = qs.filter(type=expected_type)
        return qs.first()
