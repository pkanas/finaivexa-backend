from datetime import date

from django.urls import reverse
from rest_framework import status

from apps.budgets.models import Budget
from apps.common.testing import BaseAPITestCase
from apps.common.utils import current_year_month


class BudgetTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.year, self.month = current_year_month()

    def create_budget(self, amount="100.00", category=None, **extra):
        return Budget.objects.create(
            user=self.user,
            category=category,
            amount=amount,
            month=self.month,
            year=self.year,
            **extra,
        )

    def test_crud_and_utilization(self):
        self.transaction("60.00")
        created = self.client.post(
            reverse("budgets:budget-list"),
            {
                "amount": "100.00", "month": self.month, "year": self.year,
                "alert_threshold": "80.00",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        budget = Budget.objects.get(user=self.user, category=None)

        detail = self.client.get(reverse("budgets:budget-detail", args=[budget.pk]))
        self.assertEqual(str(detail.data["data"]["spent"]), "60.00")
        self.assertEqual(detail.data["data"]["utilization_percentage"], 60.0)
        self.assertEqual(detail.data["data"]["status"], "safe")

        self.transaction("30.00")
        detail = self.client.get(reverse("budgets:budget-detail", args=[budget.pk]))
        self.assertEqual(str(detail.data["data"]["spent"]), "90.00")
        self.assertEqual(detail.data["data"]["status"], "warning")
        self.assertTrue(detail.data["data"]["is_alert"])

    def test_over_budget_status(self):
        budget = self.create_budget("100.00")
        self.transaction("150.00")
        detail = self.client.get(reverse("budgets:budget-detail", args=[budget.pk]))
        self.assertEqual(detail.data["data"]["status"], "over")
        self.assertEqual(str(detail.data["data"]["remaining"]), "-50.00")

    def test_category_budget_only_counts_its_category(self):
        food = self.category()
        other = self.category(name="Shopping")
        budget = self.create_budget("200.00", category=food)
        self.transaction("30.00", category=food)
        self.transaction("90.00", category=other)

        detail = self.client.get(reverse("budgets:budget-detail", args=[budget.pk]))
        self.assertEqual(str(detail.data["data"]["spent"]), "30.00")

    def test_summary_and_alerts_actions(self):
        food = self.category()
        self.create_budget("100.00")
        self.create_budget("500.00", category=food)
        self.transaction("90.00")  # overall alert

        summary = self.client.get(reverse("budgets:budget-summary"))
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(len(summary.data["data"]["budgets"]), 2)

        alerts = self.client.get(reverse("budgets:budget-alerts"))
        self.assertEqual(len(alerts.data["data"]), 1)
        self.assertEqual(alerts.data["data"][0]["category"], "Overall")

    def test_duplicate_budget_scope_rejected(self):
        self.create_budget("100.00")
        response = self.client.post(
            reverse("budgets:budget-list"),
            {"amount": "50.00", "month": self.month, "year": self.year},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
