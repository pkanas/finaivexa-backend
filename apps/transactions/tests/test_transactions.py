from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.common.testing import BaseAPITestCase
from apps.transactions.models import Transaction

User = get_user_model()


class TransactionTests(BaseAPITestCase):
    def test_crud_is_scoped_to_user(self):
        created = self.client.post(
            reverse("transactions:transaction-list"),
            {
                "category_id": self.category().pk,
                "type": "expense",
                "amount": "25.50",
                "description": "Lunch",
                "date": date.today().isoformat(),
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        transaction_id = created.data["data"]["id"]

        listed = self.client.get(reverse("transactions:transaction-list"))
        self.assertEqual(listed.data["data"]["count"], 1)

        detail = self.client.get(
            reverse("transactions:transaction-detail", args=[transaction_id])
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["data"]["category"]["name"], "Food & Dining")

        updated = self.client.patch(
            reverse("transactions:transaction-detail", args=[transaction_id]),
            {"amount": "30.00"},
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.get(pk=transaction_id).amount, Decimal("30.00"))

        deleted = self.client.delete(
            reverse("transactions:transaction-detail", args=[transaction_id])
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_filtering_search_and_pagination(self):
        food = self.category()
        salary = self.category(category_type="income")
        self.transaction("10.00", description="Coffee", category=food)
        self.transaction("200.00", description="Groceries", category=food)
        self.transaction("1000.00", category_type="income", category=salary)

        by_type = self.client.get(reverse("transactions:transaction-list"), {"type": "income"})
        self.assertEqual(by_type.data["data"]["count"], 1)

        by_category = self.client.get(
            reverse("transactions:transaction-list"), {"category": food.pk}
        )
        self.assertEqual(by_category.data["data"]["count"], 2)

        by_date = self.client.get(
            reverse("transactions:transaction-list"),
            {"date_from": date.today().isoformat(), "date_to": date.today().isoformat()},
        )
        self.assertEqual(by_date.data["data"]["count"], 3)

        searched = self.client.get(reverse("transactions:transaction-list"), {"search": "Coffee"})
        self.assertEqual(searched.data["data"]["count"], 1)

        paginated = self.client.get(
            reverse("transactions:transaction-list"), {"page_size": 2}
        )
        self.assertEqual(len(paginated.data["data"]["results"]), 2)
        self.assertEqual(paginated.data["data"]["count"], 3)

    def test_stats_and_category_type_validation(self):
        self.transaction("100.00", category_type="income")
        self.transaction("40.00")
        response = self.client.get(reverse("transactions:transaction-stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["data"]["total_income"]), "100.00")
        self.assertEqual(str(response.data["data"]["total_expenses"]), "40.00")
        self.assertEqual(str(response.data["data"]["balance"]), "60.00")

        invalid = self.client.post(
            reverse("transactions:transaction-list"),
            {
                "category_id": self.category(category_type="income").pk,
                "type": "expense",
                "amount": "10.00",
                "description": "Mismatch",
                "date": date.today().isoformat(),
            },
            format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_see_other_users_transactions(self):
        other = User.objects.create_user(email="other@example.com", password="StrongPass123!")
        foreign = Transaction.objects.create(
            user=other,
            type=Transaction.Type.EXPENSE,
            amount=Decimal("500"),
            description="Foreign",
            date=date.today(),
        )
        response = self.client.get(
            reverse("transactions:transaction-detail", args=[foreign.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse("transactions:transaction-list")).data["data"]["count"], 0)

    def test_old_date_filter(self):
        self.transaction("10.00", tx_date=date.today() - timedelta(days=40))
        response = self.client.get(
            reverse("transactions:transaction-list"),
            {"date_to": (date.today() - timedelta(days=30)).isoformat()},
        )
        self.assertEqual(response.data["data"]["count"], 1)
