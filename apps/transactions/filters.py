from django_filters import rest_framework as filters

from .models import Transaction


class TransactionFilter(filters.FilterSet):
    type = filters.ChoiceFilter(choices=Transaction.Type.choices)
    category = filters.NumberFilter(field_name="category_id")
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")
    year = filters.NumberFilter(field_name="date__year")
    month = filters.NumberFilter(field_name="date__month")
    min_amount = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    payment_method = filters.CharFilter(lookup_expr="iexact")
    is_recurring = filters.BooleanFilter()

    class Meta:
        model = Transaction
        fields = (
            "type", "category", "date_from", "date_to", "year", "month",
            "min_amount", "max_amount", "payment_method", "is_recurring",
        )
