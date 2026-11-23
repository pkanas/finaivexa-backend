from rest_framework.routers import DefaultRouter

from . import views

app_name = "transactions"

router = DefaultRouter()
router.register(r"", views.TransactionViewSet, basename="transaction")

urlpatterns = router.urls
