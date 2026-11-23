from rest_framework import serializers

from apps.categories.models import Category
from apps.categories.serializers import CategorySerializer
from apps.categories.services import CategoryService

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Transaction
        fields = (
            "id", "category", "category_id", "type", "amount", "description",
            "date", "payment_method", "notes", "is_recurring", "source",
            "created_at", "updated_at",
        )
        read_only_fields = ("source", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        category = attrs.get("category", getattr(self.instance, "category", None))
        tx_type = attrs.get("type", getattr(self.instance, "type", None))

        if category and request:
            resolved = CategoryService.resolve_for_user(
                getattr(category, "id", category), request.user, expected_type=tx_type
            )
            if resolved is None:
                raise serializers.ValidationError(
                    {"category_id": "Invalid category for this transaction type."}
                )
            attrs["category"] = resolved
        return attrs


class TransactionStatsQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        if attrs.get("date_from") and attrs.get("date_to"):
            if attrs["date_from"] > attrs["date_to"]:
                raise serializers.ValidationError("date_from must be before date_to.")
        return attrs
