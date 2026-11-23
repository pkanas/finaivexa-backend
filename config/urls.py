"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

API = "api/v1/"

urlpatterns = [
    path("admin/", admin.site.urls),

    # Authentication & profile
    path(f"{API}auth/", include("apps.accounts.urls")),

    # Core finance modules
    path(f"{API}categories/", include("apps.categories.urls")),
    path(f"{API}transactions/", include("apps.transactions.urls")),
    path(f"{API}budgets/", include("apps.budgets.urls")),
    path(f"{API}dashboard/", include("apps.dashboard.urls")),
    path(f"{API}reports/", include("apps.reports.urls")),
    path(f"{API}groups/", include("apps.groups.urls")),
    path(f"{API}ai/", include("apps.ai_assistant.urls")),

    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
