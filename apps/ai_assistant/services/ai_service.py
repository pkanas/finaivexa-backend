"""AI features with deterministic, ORM-only fallbacks.

Safety design
-------------
The language model is used ONLY to (a) suggest a category id from an explicit
list and (b) classify a natural-language question into one of a fixed set of
intents with tightly validated parameters. Every financial number is produced
by the Django ORM inside :meth:`AIService._execute_intent`; the model never
sees the database, never writes SQL and cannot influence queryset structure.
"""
import json
import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.budgets.models import Budget
from apps.budgets.services import BudgetService
from apps.categories.models import Category
from apps.categories.services import CategoryService
from apps.common.utils import (
    current_year_month,
    month_bounds,
    parse_date,
    shift_month,
    to_money,
)
from apps.reports.services import ReportService
from apps.transactions.models import Transaction
from apps.transactions.serializers import TransactionSerializer
from apps.transactions.services import TransactionService

from .openai_service import OpenAIService

CATEGORY_SYSTEM = (
    "You classify expenses into one of the provided categories. "
    "Reply with ONLY a JSON object: {\"category_id\": <integer from the list>, "
    "\"confidence\": <number between 0 and 1>}. "
    "Never invent a category id and never output anything else."
)

ANALYZE_SYSTEM = (
    "You are a financial analyst. Using ONLY the provided JSON data, reply with "
    "a JSON object with keys: summary (string), insights (array of at most 4 "
    "short strings), suggestions (array of at most 3 short strings). "
    "Do not invent figures and do not mention databases or SQL."
)

RECOMMEND_SYSTEM = (
    "You are a budgeting advisor. In one or two sentences, give a practical "
    "budget tip based on the provided data. Do not invent figures."
)

ANSWER_SYSTEM = (
    "You are a concise personal-finance assistant. Answer the user's question "
    "in at most 3 sentences using ONLY the provided JSON data. Do not invent "
    "numbers, do not mention databases, SQL, tables or queries."
)

QUERY_INTENT_SYSTEM = (
    "You are a strict intent parser for a personal finance app. "
    "Return ONLY a JSON object with exactly two keys: 'intent' and 'parameters'.\n"
    "Allowed intents: total_income, total_expenses, balance, spending_by_category, "
    "spending_in_period, budget_status, recent_transactions, compare_months, help.\n"
    "Allowed parameter keys (include only values you are certain about): "
    "start_date, end_date (YYYY-MM-DD), category_name, month (1-12), "
    "year (e.g. 2026), limit (1-20).\n"
    "Never include SQL, code, field names or any other keys. "
    "If unsure, use intent 'help' with empty parameters."
)

ALLOWED_INTENTS = frozenset(
    {
        "total_income", "total_expenses", "balance", "spending_by_category",
        "spending_in_period", "budget_status", "recent_transactions",
        "compare_months", "help",
    }
)
ALLOWED_PARAM_KEYS = frozenset(
    {"start_date", "end_date", "category_name", "month", "year", "limit"}
)

CATEGORY_KEYWORDS = {
    "Food & Dining": (
        "restaurant", "cafe", "coffee", "pizza", "lunch", "dinner", "breakfast",
        "food", "starbucks", "burger", "sushi", "delivery",
    ),
    "Groceries": ("grocery", "groceries", "supermarket", "walmart", "whole foods", "market"),
    "Transportation": ("uber", "taxi", "fuel", "gas", "petrol", "bus", "train", "metro", "parking", "transport"),
    "Housing & Rent": ("rent", "mortgage", "landlord", "housing"),
    "Bills & Utilities": ("electric", "water", "internet", "utility", "utilities", "phone bill", "wifi"),
    "Shopping": ("amazon", "shopping", "clothes", "shoes", "electronics"),
    "Entertainment": ("netflix", "spotify", "movie", "cinema", "concert", "game", "entertainment"),
    "Healthcare": ("pharmacy", "doctor", "hospital", "clinic", "medicine", "health"),
    "Education": ("course", "tuition", "book", "school", "udemy", "education"),
    "Travel": ("flight", "hotel", "airbnb", "trip", "travel", "booking"),
    "Personal Care": ("salon", "barber", "spa", "gym", "beauty"),
}

MONTH_NAMES = {
    name: index
    for index, name in enumerate(
        (
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ),
        start=1,
    )
}


def json_safe(value):
    """Convert Decimals/dates to JSON-serialisable primitives."""
    if isinstance(value, Decimal):
        # Keep monetary precision: never round-trip currency through a float.
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


class AIService:
    def __init__(self, openai_service=None):
        self.openai = openai_service or OpenAIService()

    # ------------------------------------------------------------------
    # 1. Automatic categorisation
    # ------------------------------------------------------------------
    def categorize(self, user, description, amount=None):
        options = list(
            CategoryService.visible_to(user, Category.Type.EXPENSE).values("id", "name")
        )
        payload = {
            "description": description,
            "amount": str(amount) if amount is not None else None,
            "categories": [{"id": o["id"], "name": o["name"]} for o in options],
        }

        chosen = None
        confidence = 0.0
        source = "fallback"
        result = self.openai.json_completion(
            CATEGORY_SYSTEM, json.dumps(json_safe(payload))
        )
        if result:
            try:
                category_id = int(result.get("category_id"))
            except (TypeError, ValueError):
                category_id = None
            match = next((o for o in options if o["id"] == category_id), None)
            if match:
                chosen = match
                source = "ai"
                try:
                    confidence = float(result.get("confidence", 0.8))
                except (TypeError, ValueError):
                    confidence = 0.8

        if chosen is None:
            rule_name = self._keyword_category(description)
            if rule_name:
                chosen = next(
                    (o for o in options if o["name"].lower() == rule_name.lower()), None
                )
                confidence = 0.6
            if chosen is None:
                chosen = next(
                    (
                        o for o in options
                        if o["name"].lower() in {"other expense", "other"}
                    ),
                    None,
                )
                confidence = 0.0

        return {
            "category_id": chosen["id"] if chosen else None,
            "category": chosen["name"] if chosen else None,
            "confidence": round(confidence, 2),
            "source": source,
        }

    @staticmethod
    def _keyword_category(description):
        text = (description or "").lower()
        best, hits = None, 0
        for name, keywords in CATEGORY_KEYWORDS.items():
            count = sum(1 for keyword in keywords if keyword in text)
            if count > hits:
                best, hits = name, count
        return best

    # ------------------------------------------------------------------
    # 2. Monthly spending analysis
    # ------------------------------------------------------------------
    def analyze_spending(self, user, year=None, month=None):
        year = year or current_year_month()[0]
        month = month or current_year_month()[1]
        report = ReportService.monthly(user, year, month)
        previous_year, previous_month = shift_month(year, month, -1)
        previous = TransactionService.totals(
            user, *month_bounds(previous_year, previous_month)
        )

        expenses = report["summary"]["total_expenses"]
        previous_expenses = previous["total_expenses"]
        change = 0.0
        if previous_expenses:
            change = float(
                ((expenses - previous_expenses) / previous_expenses * 100).quantize(
                    Decimal("0.01")
                )
            )

        payload = {
            "period": report["period"],
            "total_income": report["summary"]["total_income"],
            "total_expenses": expenses,
            "net": report["summary"]["balance"],
            "previous_expenses": previous_expenses,
            "expense_change_pct": change,
            "top_categories": report["categories"][:5],
        }

        result = self.openai.json_completion(
            ANALYZE_SYSTEM, json.dumps(json_safe(payload))
        )
        used_ai = False
        if result and isinstance(result.get("insights"), list):
            summary = str(result.get("summary") or "").strip()
            insights = [str(item) for item in result["insights"][:4]]
            suggestions = [
                str(item) for item in (result.get("suggestions") or [])[:3]
            ]
            used_ai = True
        else:
            summary, insights, suggestions = self._deterministic_analysis(payload)

        return {
            **payload,
            "summary": summary,
            "insights": insights,
            "suggestions": suggestions,
            "source": "ai" if used_ai else "fallback",
        }

    @staticmethod
    def _deterministic_analysis(payload):
        insights = []
        top = payload["top_categories"][0] if payload["top_categories"] else None
        if top:
            insights.append(
                f"Your largest expense category was {top['category']} "
                f"({top['percentage']}% of total spending)."
            )
        change = payload["expense_change_pct"]
        if change > 10:
            insights.append(f"Spending rose {change}% compared with the previous month.")
        elif change < -10:
            insights.append(f"Spending fell {abs(change)}% compared with the previous month.")
        else:
            insights.append("Spending was broadly stable compared with last month.")
        if payload["net"] < 0:
            insights.append("Expenses exceeded income for this period.")

        suggestions = []
        if top:
            suggestions.append(f"Review your {top['category']} spending and set a monthly limit.")
        suggestions.append("Track recurring subscriptions and cancel unused ones.")
        suggestions.append("Aim to save at least 20% of your monthly income.")

        summary = (
            f"You spent {payload['total_expenses']} in {payload['period']} "
            f"against income of {payload['total_income']}."
        )
        return summary, insights, suggestions

    # ------------------------------------------------------------------
    # 3. Budget recommendations
    # ------------------------------------------------------------------
    def recommend_budgets(self, user):
        year, month = current_year_month()
        start = timezone.localdate() - timedelta(days=90)
        rows = (
            Transaction.objects.filter(
                user=user,
                type=Transaction.Type.EXPENSE,
                date__gte=start,
                category__isnull=False,
            )
            .values("category_id", "category__name")
            .annotate(total=Sum("amount"))
        )
        existing = {
            budget.category_id: budget.amount
            for budget in Budget.objects.filter(
                user=user, year=year, month=month, is_active=True, category__isnull=False
            )
        }

        recommendations = []
        for row in rows:
            average = to_money((row["total"] or Decimal(0)) / 3)
            if average <= 0:
                continue
            suggested = self._round_up(average)
            current = Decimal(existing.get(row["category_id"], 0))
            if current == 0:
                action = "create"
            elif suggested > current * Decimal("1.1"):
                action = "increase"
            elif suggested < current * Decimal("0.9"):
                action = "decrease"
            else:
                action = "maintain"
            recommendations.append(
                {
                    "category_id": row["category_id"],
                    "category": row["category__name"],
                    "average_monthly_spend": average,
                    "current_budget": to_money(current),
                    "recommended_budget": to_money(suggested),
                    "action": action,
                    "reason": (
                        f"You spent an average of {average} on "
                        f"{row['category__name']} over the last 3 months."
                    ),
                }
            )

        advice = self.openai.text_completion(
            RECOMMEND_SYSTEM,
            json.dumps(json_safe({"recommendations": recommendations})),
        )
        used_ai = bool(advice)
        if not advice:
            advice = (
                "Base each category budget on your recent average spending and "
                "review it at the end of every month."
            )
        return {
            "year": year,
            "month": month,
            "recommendations": recommendations,
            "advice": advice,
            "source": "ai" if used_ai else "fallback",
        }

    @staticmethod
    def _round_up(amount):
        return Decimal(math.ceil(amount / 10) * 10)

    # ------------------------------------------------------------------
    # 4. Unusual expense detection
    # ------------------------------------------------------------------
    def detect_unusual(self, user):
        today = timezone.localdate()
        recent_start = today - timedelta(days=30)
        history_start = today - timedelta(days=90)
        transactions = list(
            Transaction.objects.filter(
                user=user,
                type=Transaction.Type.EXPENSE,
                date__gte=history_start,
            )
            .select_related("category")
            .order_by("date")
        )

        by_category = {}
        for transaction in transactions:
            by_category.setdefault(transaction.category_id, []).append(transaction.amount)

        unusual = []
        for transaction in transactions:
            if transaction.date < recent_start:
                continue
            amounts = by_category.get(transaction.category_id, [])
            if len(amounts) < 3:
                continue
            average = sum(amounts, Decimal(0)) / Decimal(len(amounts))
            if average <= 0:
                continue
            ratio = transaction.amount / average
            if ratio >= 2:
                unusual.append(
                    {
                        "transaction_id": transaction.id,
                        "description": transaction.description,
                        "amount": to_money(transaction.amount),
                        "date": transaction.date,
                        "category": transaction.category.name if transaction.category else "Uncategorized",
                        "category_average": to_money(average),
                        "ratio": round(float(ratio), 2),
                    }
                )
        unusual.sort(key=lambda item: item["ratio"], reverse=True)
        return unusual[:20]

    # ------------------------------------------------------------------
    # 5. Natural-language financial queries (no SQL, ever)
    # ------------------------------------------------------------------
    def answer_query(self, user, question):
        raw_intent = self.openai.json_completion(QUERY_INTENT_SYSTEM, question)
        intent_data = self._sanitize_intent(raw_intent)
        used_ai = intent_data is not None
        if intent_data is None:
            intent_data = self._fallback_intent(question)

        # _execute_intent is the ONLY place that reads financial data. It uses
        # fixed querysets and validated parameters; model output cannot inject
        # SQL, field names or arbitrary filters.
        data = self._execute_intent(user, intent_data["intent"], intent_data["parameters"])

        answer = self.openai.text_completion(
            ANSWER_SYSTEM,
            f"Question: {question}\nData: {json.dumps(json_safe(data))}",
        )
        if answer:
            used_ai = True
        else:
            answer = self._template_answer(intent_data["intent"], data)

        return {
            "intent": intent_data["intent"],
            "parameters": json_safe(intent_data["parameters"]),
            "data": json_safe(data),
            "answer": answer,
            "source": "ai" if used_ai else "fallback",
        }

    @staticmethod
    def _sanitize_intent(raw):
        """Whitelist the intent and every parameter the model may supply."""
        if not isinstance(raw, dict):
            return None
        intent = str(raw.get("intent", "")).strip().lower()
        if intent not in ALLOWED_INTENTS:
            return None
        raw_params = raw.get("parameters")
        if not isinstance(raw_params, dict):
            raw_params = {}
        params = {}
        for key, value in raw_params.items():
            if key not in ALLOWED_PARAM_KEYS:
                continue
            if key in {"start_date", "end_date"}:
                parsed = parse_date(value)
                if parsed:
                    params[key] = parsed
            elif key == "category_name":
                if isinstance(value, str) and 0 < len(value.strip()) <= 100:
                    params[key] = value.strip()
            else:
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    continue
                bounds = {
                    "month": (1, 12), "year": (2000, 2100), "limit": (1, 20),
                }[key]
                if bounds[0] <= number <= bounds[1]:
                    params[key] = number
        return {"intent": intent, "parameters": params}

    @staticmethod
    def _fallback_intent(question):
        text = (question or "").lower()
        params = {}
        current_year, current_month = current_year_month()

        year_match = re.search(r"\b(20\d{2})\b", text)
        if year_match:
            params["year"] = int(year_match.group(1))
        for name, number in MONTH_NAMES.items():
            if re.search(rf"\b{name}\b", text):
                params["month"] = number
                params["year"] = params.get("year", current_year)
                break
        if "last month" in text:
            params["year"], params["month"] = shift_month(current_year, current_month, -1)
        elif "this month" in text or "current month" in text:
            params["year"], params["month"] = current_year, current_month

        if "budget" in text:
            intent = "budget_status"
        elif "balance" in text or "how much do i have" in text:
            intent = "balance"
        elif "income" in text or "earn" in text or "salary" in text:
            intent = "total_income"
        elif "compare" in text or "versus" in text or "vs " in text:
            intent = "compare_months"
        elif "recent" in text or "last transactions" in text:
            intent = "recent_transactions"
            params["limit"] = 5
        elif any(word in text for word in ("spend", "spent", "expense", "cost", "bought")):
            intent = "spending_by_category" if " on " in text or "category" in text else "total_expenses"
        else:
            intent = "help"
        return {"intent": intent, "parameters": params}

    @staticmethod
    def _execute_intent(user, intent, params):
        """Run a predetermined, user-scoped ORM query for a validated intent."""
        start = params.get("start_date")
        end = params.get("end_date")

        if intent == "help":
            return {
                "message": "Ask about your income, expenses, balance, budgets, categories or recent transactions.",
                "supported_intents": sorted(ALLOWED_INTENTS),
            }

        if intent in {"total_income", "total_expenses", "balance"}:
            totals = TransactionService.totals(user, start, end)
            return {"period": AIService._period_label(start, end), **json_safe(totals)}

        if intent in {"spending_by_category", "spending_in_period"}:
            if not start or not end:
                year = params.get("year", current_year_month()[0])
                month = params.get("month", current_year_month()[1])
                start, end = month_bounds(year, month)
            breakdown = TransactionService.category_breakdown(user, start, end)
            category_name = params.get("category_name")
            if category_name:
                breakdown = [
                    row for row in breakdown
                    if category_name.lower() in row["category"].lower()
                ]
            return {
                "period": AIService._period_label(start, end),
                "total_expenses": json_safe(
                    sum((Decimal(str(row["total"])) for row in breakdown), Decimal(0))
                ),
                "categories": json_safe(breakdown),
            }

        if intent == "budget_status":
            return json_safe(
                BudgetService.summary(
                    user, params.get("year"), params.get("month")
                )
            )

        if intent == "recent_transactions":
            limit = params.get("limit", 5)
            transactions = TransactionService.for_user(user)[:limit]
            return {
                "transactions": TransactionSerializer(
                    transactions, many=True, context={"request": None}
                ).data
            }

        if intent == "compare_months":
            year, month = current_year_month()
            current = TransactionService.totals(user, *month_bounds(year, month))
            previous_year, previous_month = shift_month(year, month, -1)
            previous = TransactionService.totals(
                user, *month_bounds(previous_year, previous_month)
            )
            return {"current": json_safe(current), "previous": json_safe(previous)}

        return {"message": "I can't help with that yet."}

    @staticmethod
    def _period_label(start, end):
        if start and end:
            return f"{start.isoformat()} to {end.isoformat()}"
        return "all time"

    @staticmethod
    def _template_answer(intent, data):
        if intent == "help":
            return data["message"]
        if intent == "total_income":
            return f"Your total income for {data['period']} was {data['total_income']}."
        if intent == "total_expenses":
            return f"Your total expenses for {data['period']} were {data['total_expenses']}."
        if intent == "balance":
            return (
                f"For {data['period']}, your income was {data['total_income']} and "
                f"expenses {data['total_expenses']}, leaving a balance of {data['balance']}."
            )
        if intent in {"spending_by_category", "spending_in_period"}:
            top = data["categories"][0] if data["categories"] else None
            if top:
                return (
                    f"You spent {data['total_expenses']} in {data['period']}; "
                    f"the largest category was {top['category']} at {top['total']} "
                    f"({top['percentage']}%)."
                )
            return f"No spending was recorded for {data['period']}."
        if intent == "budget_status":
            alerts = [b for b in data["budgets"] if b["is_alert"]]
            if alerts:
                return (
                    f"{len(alerts)} budget(s) have reached their alert threshold, "
                    f"with total budget {data['total_budget']} and spent {data['total_spent']}."
                )
            return f"You have spent {data['total_spent']} of your {data['total_budget']} budget."
        if intent == "recent_transactions":
            count = len(data["transactions"])
            return f"Here are your {count} most recent transactions."
        if intent == "compare_months":
            return (
                f"This month's expenses were {data['current']['total_expenses']} "
                f"versus {data['previous']['total_expenses']} last month."
            )
        return "I couldn't answer that question."
