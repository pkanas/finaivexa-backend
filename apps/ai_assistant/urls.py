from django.urls import path

from . import views

app_name = "ai_assistant"

urlpatterns = [
    path("categorize", views.CategorizeView.as_view(), name="categorize"),
    path("analyze-spending", views.SpendingAnalysisView.as_view(), name="analyze-spending"),
    path(
        "recommend-budgets",
        views.BudgetRecommendationsView.as_view(),
        name="recommend-budgets",
    ),
    path("unusual-expenses", views.UnusualExpensesView.as_view(), name="unusual-expenses"),
    path("query", views.FinancialQueryView.as_view(), name="query"),
]
