from rest_framework.routers import DefaultRouter

from . import views

app_name = "budgets"

router = DefaultRouter()
router.register(r"", views.BudgetViewSet, basename="budget")

urlpatterns = router.urls
