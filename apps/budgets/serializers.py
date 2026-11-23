from rest_framework import serializers

from apps.categories.models import Category
from apps.categories.serializers import CategorySerializer
from apps.categories.services import CategoryService

from .models import Budget
from .services import BudgetService


class BudgetSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(),
        write_only=True, required=False, allow_null=True,
    )
    spent = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    utilization_percentage = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    is_alert = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        # Duplicate scopes are validated explicitly in validate() because the
        # model constraint spans a read-only nested field + a write-only id.
        validators = []
        fields = (
            "id", "user", "category", "category_id", "amount", "month", "year",
            "alert_threshold", "is_active", "spent", "remaining",
            "utilization_percentage", "status", "is_alert", "created_at",
        )
        read_only_fields = ("created_at",)

    def _utilization(self, obj):
        if not hasattr(self, "_util_cache"):
            self._util_cache = {}
        if obj.pk not in self._util_cache:
            self._util_cache[obj.pk] = BudgetService.utilization(obj)
        return self._util_cache[obj.pk]

    def get_spent(self, obj) -> str:
        return self._utilization(obj)["spent"]

    def get_remaining(self, obj) -> str:
        return self._utilization(obj)["remaining"]

    def get_utilization_percentage(self, obj) -> float:
        return self._utilization(obj)["utilization_percentage"]

    def get_status(self, obj) -> str:
        return self._utilization(obj)["status"]

    def get_is_alert(self, obj) -> bool:
        return self._utilization(obj)["is_alert"]

    def validate(self, attrs):
        request = self.context["request"]
        category = attrs.get("category", getattr(self.instance, "category", None))
        month = attrs.get("month", getattr(self.instance, "month", None))
        year = attrs.get("year", getattr(self.instance, "year", None))

        if category:
            resolved = CategoryService.resolve_for_user(
                getattr(category, "id", category),
                request.user,
                expected_type=Category.Type.EXPENSE,
            )
            if resolved is None:
                raise serializers.ValidationError(
                    {"category_id": "Only one of your expense categories can be used."}
                )
            attrs["category"] = resolved

        qs = Budget.objects.filter(user=request.user, month=month, year=year, category=category)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A budget for this scope and month already exists."
            )
        return attrs


class BudgetQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)
