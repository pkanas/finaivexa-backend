from rest_framework.routers import DefaultRouter

from . import views

app_name = "categories"

router = DefaultRouter()
router.register(r"", views.CategoryViewSet, basename="category")

urlpatterns = router.urls
