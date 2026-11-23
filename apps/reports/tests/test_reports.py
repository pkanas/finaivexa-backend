from calendar import monthrange

from django.urls import reverse
from rest_framework import status

from apps.common.testing import BaseAPITestCase
from apps.common.utils import current_year_month


class ReportTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.year, self.month = current_year_month()

    def test_monthly_report(self):
        self.transaction("100.00")
        response = self.client.get(
            reverse("reports:monthly"), {"year": self.year, "month": self.month}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["type"], "monthly")
        self.assertEqual(str(data["summary"]["total_expenses"]), "100.00")
        self.assertEqual(len(data["daily"]), monthrange(self.year, self.month)[1])

    def test_yearly_report(self):
        self.transaction("100.00")
        response = self.client.get(reverse("reports:yearly"), {"year": self.year})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(len(data["months"]), 12)
        self.assertEqual(str(data["summary"]["total_expenses"]), "100.00")

    def test_category_report(self):
        self.transaction("70.00")
        self.transaction("30.00", category=self.category(name="Shopping"))
        start = f"{self.year}-{self.month:02d}-01"
        end = f"{self.year}-{self.month:02d}-28"
        response = self.client.get(
            reverse("reports:category"), {"start_date": start, "end_date": end}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        categories = response.data["data"]["categories"]
        self.assertEqual(len(categories), 2)
        self.assertEqual(str(categories[0]["total"]), "70.00")

    def test_invalid_date_range(self):
        response = self.client.get(
            reverse("reports:category"),
            {"start_date": "2026-02-02", "end_date": "2026-01-01"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
