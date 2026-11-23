from django_filters import rest_framework as filters

from .models import Category


class CategoryFilter(filters.FilterSet):
    type = filters.ChoiceFilter(choices=Category.Type.choices)
    is_default = filters.BooleanFilter()
    name = filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Category
        fields = ("type", "is_default", "name")
