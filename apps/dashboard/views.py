from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers, views
from rest_framework.permissions import IsAuthenticated

from apps.common.responses import api_success

from .services import DashboardService


class PeriodQuery(serializers.Serializer):
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)


class MonthlySpendingQuery(serializers.Serializer):
    months = serializers.IntegerField(required=False, min_value=1, max_value=24, default=12)


class RecentTransactionsQuery(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=5)


class SummaryView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Financial overview")
    def get(self, request):
        return api_success(DashboardService.summary(request.user))


class MonthlySpendingView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[MonthlySpendingQuery],
        responses=OpenApiTypes.OBJECT,
        summary="Monthly income/expense series for charts",
    )
    def get(self, request):
        query = MonthlySpendingQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        return api_success(
            DashboardService.monthly_spending(
                request.user, query.validated_data["months"]
            )
        )


class CategorySpendingView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PeriodQuery],
        responses=OpenApiTypes.OBJECT,
        summary="Category-wise spending for a month",
    )
    def get(self, request):
        query = PeriodQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        return api_success(
            DashboardService.category_spending(
                request.user,
                year=query.validated_data.get("year"),
                month=query.validated_data.get("month"),
            )
        )


class RecentTransactionsView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[RecentTransactionsQuery],
        responses=OpenApiTypes.OBJECT,
        summary="Most recent transactions",
    )
    def get(self, request):
        query = RecentTransactionsQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        return api_success(
            DashboardService.recent_transactions(
                request.user, query.validated_data["limit"]
            )
        )
