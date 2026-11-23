from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("monthly", views.MonthlyReportView.as_view(), name="monthly"),
    path("yearly", views.YearlyReportView.as_view(), name="yearly"),
    path("category", views.CategoryReportView.as_view(), name="category"),
]
