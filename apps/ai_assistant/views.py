"""AI assistant endpoints."""
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import views
from rest_framework.permissions import IsAuthenticated

from apps.common.responses import api_success

from .serializers import AnalysisQuerySerializer, CategorizeSerializer, FinancialQuerySerializer
from .services.ai_service import AIService


class AIBaseView(views.APIView):
    permission_classes = [IsAuthenticated]

    @property
    def ai(self):
        if not hasattr(self, "_ai"):
            self._ai = AIService()
        return self._ai


class CategorizeView(AIBaseView):
    @extend_schema(
        request=CategorizeSerializer,
        responses=OpenApiTypes.OBJECT,
        summary="Suggest a category for a transaction description",
    )
    def post(self, request):
        serializer = CategorizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return api_success(
            self.ai.categorize(
                request.user,
                serializer.validated_data["description"],
                amount=serializer.validated_data.get("amount"),
            )
        )


class SpendingAnalysisView(AIBaseView):
    @extend_schema(
        request=AnalysisQuerySerializer,
        responses=OpenApiTypes.OBJECT,
        summary="AI analysis of monthly spending",
    )
    def post(self, request):
        serializer = AnalysisQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return api_success(
            self.ai.analyze_spending(
                request.user,
                year=serializer.validated_data.get("year"),
                month=serializer.validated_data.get("month"),
            )
        )


class BudgetRecommendationsView(AIBaseView):
    @extend_schema(
        request=None,
        responses=OpenApiTypes.OBJECT,
        summary="AI budget recommendations based on recent averages",
    )
    def post(self, request):
        return api_success(self.ai.recommend_budgets(request.user))


class UnusualExpensesView(AIBaseView):
    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        summary="Detect statistically unusual recent expenses",
    )
    def get(self, request):
        return api_success(self.ai.detect_unusual(request.user))


class FinancialQueryView(AIBaseView):
    @extend_schema(
        request=FinancialQuerySerializer,
        responses=OpenApiTypes.OBJECT,
        summary="Ask a natural-language question about your finances",
    )
    def post(self, request):
        serializer = FinancialQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return api_success(
            self.ai.answer_query(request.user, serializer.validated_data["question"])
        )
