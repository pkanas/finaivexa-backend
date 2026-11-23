from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("summary", views.SummaryView.as_view(), name="summary"),
    path("monthly-spending", views.MonthlySpendingView.as_view(), name="monthly-spending"),
    path("category-spending", views.CategorySpendingView.as_view(), name="category-spending"),
    path("recent-transactions", views.RecentTransactionsView.as_view(), name="recent-transactions"),
]
