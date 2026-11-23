from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.common.mixins import EnvelopeMixin

from .filters import CategoryFilter
from .models import Category
from .serializers import CategorySerializer
from .services import CategoryService


class CategoryViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    """List/create/update the current user's categories plus global defaults."""

    serializer_class = CategorySerializer
    filterset_class = CategoryFilter
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")
    ordering = ("type", "name")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Category.objects.none()
        return CategoryService.visible_to(self.request.user)

    def perform_destroy(self, instance):
        if instance.is_default or instance.user_id is None:
            raise ValidationError("Default categories cannot be deleted.")
        if instance.transactions.exists() or instance.budgets.exists():
            raise ValidationError(
                "This category is in use. Reassign or remove its records first."
            )
        instance.delete()
