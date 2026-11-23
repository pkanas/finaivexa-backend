from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import EnvelopeMixin

from .filters import TransactionFilter
from .models import Transaction
from .serializers import TransactionSerializer, TransactionStatsQuerySerializer
from .services import TransactionService


class TransactionViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    """CRUD + search/filter/pagination, scoped to the authenticated user."""

    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter
    search_fields = ("description", "notes", "payment_method")
    ordering_fields = ("date", "amount", "created_at")
    ordering = ("-date", "-created_at")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Transaction.objects.none()
        return TransactionService.for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        parameters=[TransactionStatsQuerySerializer],
        responses=OpenApiTypes.OBJECT,
        summary="Income/expense totals for an optional date range",
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        query = TransactionStatsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(
            TransactionService.totals(
                request.user,
                start_date=query.validated_data.get("date_from"),
                end_date=query.validated_data.get("date_to"),
            )
        )
