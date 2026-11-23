from decimal import Decimal

from rest_framework import serializers


class CategorizeSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255, trim_whitespace=True)
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=Decimal("0.01")
    )


class AnalysisQuerySerializer(serializers.Serializer):
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)


class FinancialQuerySerializer(serializers.Serializer):
    question = serializers.CharField(max_length=500, trim_whitespace=True)
