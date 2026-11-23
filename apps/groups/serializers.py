from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.categories.models import Category
from apps.categories.serializers import CategorySerializer

from .models import ExpenseShare, Group, GroupExpense, GroupMember, Settlement
from .services import GroupService

User = get_user_model()


class UserLiteSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "full_name")
        read_only_fields = fields


class GroupSerializer(serializers.ModelSerializer):
    created_by = UserLiteSerializer(read_only=True)
    members = UserLiteSerializer(many=True, read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = (
            "id", "name", "description", "currency", "created_by", "members",
            "member_count", "created_at",
        )
        read_only_fields = ("id", "created_by", "created_at")

    def get_member_count(self, obj) -> int:
        return obj.members.count()


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ("name", "description", "currency")
        extra_kwargs = {"description": {"required": False}, "currency": {"required": False}}

    def validate_name(self, value):
        return value.strip()

    def validate_currency(self, value):
        return (value or "USD").upper()

    def create(self, validated_data):
        return GroupService.create_group(self.context["request"].user, **validated_data)


class AddMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=GroupMember.Role.choices, required=False)

    def validate_email(self, value):
        return value.strip().lower()


class ShareInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)


class ExpenseShareSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)

    class Meta:
        model = ExpenseShare
        fields = ("id", "user", "amount", "percentage", "is_settled", "settled_at")


class GroupExpenseSerializer(serializers.ModelSerializer):
    paid_by = UserLiteSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    shares = ExpenseShareSerializer(many=True, read_only=True)

    class Meta:
        model = GroupExpense
        fields = (
            "id", "description", "amount", "date", "split_type", "paid_by",
            "category", "shares", "created_at",
        )
        read_only_fields = fields


class GroupExpenseCreateSerializer(serializers.ModelSerializer):
    paid_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(),
        required=False, allow_null=True, write_only=True,
    )
    shares = serializers.ListField(
        child=ShareInputSerializer(), required=False, write_only=True
    )

    class Meta:
        model = GroupExpense
        fields = (
            "description", "amount", "date", "split_type", "paid_by",
            "category_id", "shares",
        )

    def validate_paid_by(self, value):
        group = self.context["group"]
        if not group.is_member(value):
            raise serializers.ValidationError("The payer must be a group member.")
        return value

    def validate(self, attrs):
        split_type = attrs.get("split_type", GroupExpense.SplitType.EQUAL)
        if split_type in (GroupExpense.SplitType.CUSTOM, GroupExpense.SplitType.PERCENTAGE) and not attrs.get("shares"):
            raise serializers.ValidationError({"shares": "Shares are required for this split type."})
        return attrs

    def create(self, validated_data):
        shares = validated_data.pop("shares", None)
        return GroupService.create_expense(
            group=self.context["group"],
            shares_data=shares,
            **validated_data,
        )


class GroupMemberSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)

    class Meta:
        model = GroupMember
        fields = ("id", "user", "role", "created_at")
        read_only_fields = fields


class SettlementSerializer(serializers.ModelSerializer):
    from_user = UserLiteSerializer(read_only=True)
    to_user = UserLiteSerializer(read_only=True)

    class Meta:
        model = Settlement
        fields = ("id", "from_user", "to_user", "amount", "note", "created_at")
        read_only_fields = fields


class SettlementCreateSerializer(serializers.Serializer):
    to_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_to_user(self, value):
        if not self.context["group"].is_member(value):
            raise serializers.ValidationError("The recipient must be a group member.")
        return value

    def create(self, validated_data):
        return GroupService.create_settlement(
            group=self.context["group"],
            from_user=self.context["request"].user,
            **validated_data,
        )
