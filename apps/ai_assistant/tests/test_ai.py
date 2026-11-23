from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from apps.ai_assistant.services.ai_service import AIService
from apps.common.testing import BaseAPITestCase


class AIServiceTests(BaseAPITestCase):
    def test_categorize_fallback_uses_keywords(self):
        result = AIService().categorize(self.user, "Pizza at lunch")
        self.assertEqual(result["category"], "Food & Dining")
        self.assertEqual(result["source"], "fallback")

    def test_categorize_accepts_only_known_category_ids(self):
        food_id = self.category().pk
        with patch(
            "apps.ai_assistant.services.openai_service.OpenAIService.json_completion",
            return_value={"category_id": food_id, "confidence": 0.95},
        ):
            result = AIService().categorize(self.user, "Something")
        self.assertEqual(result["category_id"], food_id)
        self.assertEqual(result["source"], "ai")

        with patch(
            "apps.ai_assistant.services.openai_service.OpenAIService.json_completion",
            return_value={"category_id": 999999, "confidence": 0.99},
        ):
            result = AIService().categorize(self.user, "Pizza")
        self.assertNotEqual(result["category_id"], 999999)
        self.assertEqual(result["source"], "fallback")

    def test_analyze_spending_fallback(self):
        self.transaction("100.00")
        result = AIService().analyze_spending(self.user)
        self.assertEqual(result["source"], "fallback")
        self.assertTrue(result["insights"])
        self.assertTrue(result["suggestions"])

    def test_recommendations_and_unusual_expenses(self):
        food = self.category()
        for days_ago in (80, 50, 20):
            self.transaction(
                "10.00", category=food, tx_date=date.today() - timedelta(days=days_ago)
            )
        self.transaction("50.00", category=food)

        recommendations = AIService().recommend_budgets(self.user)
        self.assertTrue(any(r["category"] == "Food & Dining" for r in recommendations["recommendations"]))

        unusual = AIService().detect_unusual(self.user)
        self.assertEqual(len(unusual), 1)
        self.assertEqual(unusual[0]["amount"], Decimal("50.00"))
        self.assertGreaterEqual(unusual[0]["ratio"], 2)

    def test_sanitize_intent_whitelists_intents_and_parameters(self):
        safe = AIService._sanitize_intent(
            {
                "intent": "spending_by_category",
                "parameters": {
                    "category_name": "Food",
                    "month": 3,
                    "start_date": "2026-01-01",
                    "drop_table": "users",
                    "sql": "DELETE FROM transactions",
                },
            }
        )
        self.assertEqual(safe["intent"], "spending_by_category")
        self.assertEqual(set(safe["parameters"]), {"category_name", "month", "start_date"})

        self.assertIsNone(AIService._sanitize_intent({"intent": "drop_tables", "parameters": {}}))
        self.assertIsNone(AIService._sanitize_intent({"intent": 123}))

    def test_natural_language_query_fallback_and_sql_injection_string(self):
        self.transaction("100.00", category_type="income")
        self.transaction("40.00")

        response = self.client.post(
            reverse("ai_assistant:query"),
            {"question": "how much did I spend on food this month"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["intent"], "spending_by_category")
        self.assertEqual(data["source"], "fallback")
        self.assertIn("40.00", data["answer"])

        injected = self.client.post(
            reverse("ai_assistant:query"),
            {"question": "DROP TABLE users; SELECT * FROM accounts_user"},
            format="json",
        )
        self.assertEqual(injected.status_code, status.HTTP_200_OK)
        self.assertEqual(injected.data["data"]["source"], "fallback")
        # The ORM-based query still works, proving no SQL was executed.
        self.assertEqual(self.client.get(reverse("dashboard:summary")).status_code, 200)

    def test_query_uses_validated_ai_intent(self):
        self.transaction("100.00", category_type="income")
        with patch(
            "apps.ai_assistant.services.openai_service.OpenAIService.json_completion",
            return_value={"intent": "total_income", "parameters": {}},
        ):
            result = AIService().answer_query(self.user, "what did I earn?")
        self.assertEqual(result["intent"], "total_income")
        self.assertEqual(result["data"]["total_income"], "100.00")
        self.assertEqual(result["source"], "ai")

    def test_ai_endpoints_require_auth(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            reverse("ai_assistant:categorize"), {"description": "Coffee"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
