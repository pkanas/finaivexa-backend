from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers, views
from rest_framework.permissions import IsAuthenticated

from apps.common.responses import api_success
from apps.common.utils import current_year_month

from .services import ReportService


class PeriodQuery(serializers.Serializer):
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)


class YearQuery(serializers.Serializer):
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)


class CategoryReportQuery(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    type = serializers.ChoiceField(choices=("income", "expense"), default="expense")

    def validate(self, attrs):
        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError("start_date must be before end_date.")
        return attrs


class MonthlyReportView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PeriodQuery],
        responses=OpenApiTypes.OBJECT,
        summary="Monthly report with daily trend",
    )
    def get(self, request):
        query = PeriodQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        default_year, default_month = current_year_month()
        return api_success(
            ReportService.monthly(
                request.user,
                query.validated_data.get("year", default_year),
                query.validated_data.get("month", default_month),
            )
        )


class YearlyReportView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[YearQuery],
        responses=OpenApiTypes.OBJECT,
        summary="Yearly report with monthly totals",
    )
    def get(self, request):
        query = YearQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        return api_success(
            ReportService.yearly(
                request.user, query.validated_data.get("year", current_year_month()[0])
            )
        )


class CategoryReportView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[CategoryReportQuery],
        responses=OpenApiTypes.OBJECT,
        summary="Category-wise report for a date range",
    )
    def get(self, request):
        query = CategoryReportQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        return api_success(
            ReportService.category(
                request.user,
                data["start_date"],
                data["end_date"],
                category_type=data["type"],
            )
        )
