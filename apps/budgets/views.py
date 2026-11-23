from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import EnvelopeMixin

from .models import Budget
from .serializers import BudgetQuerySerializer, BudgetSerializer
from .services import BudgetService


class BudgetViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = BudgetSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Budget.objects.none()
        return BudgetService.for_user(self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def _period(self, request):
        query = BudgetQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return query.validated_data.get("year"), query.validated_data.get("month")

    @extend_schema(
        parameters=[BudgetQuerySerializer],
        responses=OpenApiTypes.OBJECT,
        summary="Budget utilization summary for a month",
    )
    @action(detail=False, methods=["get"])
    def summary(self, request):
        year, month = self._period(request)
        return Response(BudgetService.summary(request.user, year, month))

    @extend_schema(
        parameters=[BudgetQuerySerializer],
        responses=OpenApiTypes.OBJECT,
        summary="Budgets that reached their alert threshold",
    )
    @action(detail=False, methods=["get"])
    def alerts(self, request):
        year, month = self._period(request)
        return Response(BudgetService.alerts(request.user, year, month))
