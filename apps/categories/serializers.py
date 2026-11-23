from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault

from .models import Category
from .services import CategoryService


class CategorySerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=CurrentUserDefault())
    is_default = serializers.BooleanField(read_only=True)
    scope = serializers.CharField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "type", "icon", "color", "is_default", "scope", "user")
        extra_kwargs = {"color": {"required": False}}

    def validate_name(self, value):
        return value.strip()

    def validate(self, attrs):
        user = self.context["request"].user
        name = attrs.get("name", getattr(self.instance, "name", None))
        category_type = attrs.get("type", getattr(self.instance, "type", None))
        qs = Category.objects.filter(name__iexact=name, type=category_type, user=user)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"name": "You already have a category with this name and type."}
            )
        return attrs
