"""Shared helpers for API tests."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.transactions.models import Transaction

User = get_user_model()


class BaseAPITestCase(APITestCase):
    password = "StrongPass123!"

    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com",
            password=self.password,
            first_name="Test",
            last_name="User",
        )
        self.client.force_authenticate(user=self.user)

    def category(self, name=None, category_type="expense"):
        name = name or ("Food & Dining" if category_type == "expense" else "Salary")
        return Category.objects.get(name=name, type=category_type, user__isnull=True)

    def transaction(self, amount="50.00", category_type="expense", tx_type=None,
                    tx_date=None, description="Test transaction", category=None):
        tx_type = tx_type or ("expense" if category_type == "expense" else "income")
        if category is None:
            category = self.category(category_type=category_type)
        return Transaction.objects.create(
            user=self.user,
            category=category,
            type=tx_type,
            amount=Decimal(amount),
            description=description,
            date=tx_date or date.today(),
        )
