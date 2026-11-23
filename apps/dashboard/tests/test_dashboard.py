from django.urls import reverse
from rest_framework import status

from apps.common.testing import BaseAPITestCase


class DashboardTests(BaseAPITestCase):
    def test_summary(self):
        self.transaction("1000.00", category_type="income")
        self.transaction("250.00")
        response = self.client.get(reverse("dashboard:summary"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(str(data["total_income"]), "1000.00")
        self.assertEqual(str(data["total_expenses"]), "250.00")
        self.assertEqual(str(data["available_balance"]), "750.00")
        self.assertEqual(str(data["this_month"]["expenses"]), "250.00")

    def test_monthly_spending_series(self):
        self.transaction("100.00")
        response = self.client.get(
            reverse("dashboard:monthly-spending"), {"months": 6}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 6)
        self.assertEqual(str(response.data["data"][-1]["expenses"]), "100.00")

    def test_category_spending_and_recent_transactions(self):
        self.transaction("60.00")
        self.transaction("40.00", category=self.category(name="Shopping"))

        categories = self.client.get(reverse("dashboard:category-spending"))
        self.assertEqual(len(categories.data["data"]["categories"]), 2)
        top = categories.data["data"]["categories"][0]
        self.assertEqual(top["category"], "Food & Dining")
        self.assertEqual(top["percentage"], 60.0)

        recent = self.client.get(
            reverse("dashboard:recent-transactions"), {"limit": 1}
        )
        self.assertEqual(len(recent.data["data"]), 1)

    def test_dashboard_requires_auth(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(reverse("dashboard:summary")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
