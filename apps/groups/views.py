"""Group management, shared expenses and settlement APIs."""
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiTypes, extend_schema
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ServiceError
from apps.common.mixins import EnvelopeMixin
from apps.common.responses import api_success

from .models import Group, GroupExpense, GroupMember
from .serializers import (
    AddMemberSerializer,
    GroupCreateSerializer,
    GroupExpenseCreateSerializer,
    GroupExpenseSerializer,
    GroupMemberSerializer,
    GroupSerializer,
    SettlementCreateSerializer,
    SettlementSerializer,
)
from .services import GroupService

User = get_user_model()


class GroupAccessMixin:
    """Resolve a group and ensure the requesting user is a member."""

    def get_group(self):
        group = get_object_or_404(Group, pk=self.kwargs["group_pk"])
        if not group.is_member(self.request.user):
            raise PermissionDenied("You are not a member of this group.")
        return group

    @staticmethod
    def require_admin(group, user):
        if not group.is_admin(user):
            raise PermissionDenied("Only group admins can perform this action.")


class GroupViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.action == "create":
            return GroupCreateSerializer
        return GroupSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Group.objects.none()
        return (
            Group.objects.filter(members=self.request.user)
            .distinct()
            .prefetch_related("memberships__user", "members")
        )

    def perform_destroy(self, instance):
        if not instance.is_admin(self.request.user):
            raise PermissionDenied("Only group admins can delete a group.")
        instance.delete()

    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Net balance per member")
    @action(detail=True, methods=["get"])
    def balances(self, request, pk=None):
        return Response(GroupService.balances(self.get_object()))

    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Simplified settlement plan")
    @action(detail=True, methods=["get"], url_path="settlement-plan")
    def settlement_plan(self, request, pk=None):
        return Response(GroupService.settlement_plan(self.get_object()))


class GroupMembersView(GroupAccessMixin, APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT, summary="List group members")
    def get(self, request, group_pk):
        group = self.get_group()
        memberships = group.memberships.select_related("user").all()
        return api_success(GroupMemberSerializer(memberships, many=True).data)

    @extend_schema(
        request=AddMemberSerializer,
        responses=OpenApiTypes.OBJECT,
        summary="Add a member to the group",
    )
    def post(self, request, group_pk):
        group = self.get_group()
        self.require_admin(group, request.user)
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"email": "No user with this email exists."})
        role = serializer.validated_data.get("role", GroupMember.Role.MEMBER)
        membership, created = GroupService.add_member(group, user, role=role)
        return api_success(
            GroupMemberSerializer(membership).data,
            message="Member added." if created else "Member was already in the group.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class GroupMemberDetailView(GroupAccessMixin, APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Remove a member from the group")
    def delete(self, request, group_pk, member_pk):
        group = self.get_group()
        membership = get_object_or_404(GroupMember, pk=member_pk, group=group)
        if membership.user_id != request.user.pk:
            self.require_admin(group, request.user)
        if membership.role == GroupMember.Role.ADMIN and group.memberships.filter(
            role=GroupMember.Role.ADMIN
        ).count() == 1:
            raise ServiceError("A group must keep at least one admin.")
        membership.delete()
        return api_success(message="Member removed.")


class GroupExpensesView(GroupAccessMixin, APIView):
    @extend_schema(
        operation_id="group_expenses_list",
        responses=OpenApiTypes.OBJECT,
        summary="List shared group expenses",
    )
    def get(self, request, group_pk):
        group = self.get_group()
        expenses = (
            group.expenses.select_related("paid_by", "category")
            .prefetch_related("shares__user")
            .all()
        )
        return api_success(GroupExpenseSerializer(expenses, many=True).data)

    @extend_schema(
        operation_id="group_expense_create",
        request=GroupExpenseCreateSerializer,
        responses=OpenApiTypes.OBJECT,
        summary="Create and split a shared expense",
    )
    def post(self, request, group_pk):
        group = self.get_group()
        serializer = GroupExpenseCreateSerializer(
            data=request.data, context={"group": group, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        expense = serializer.save()
        return api_success(
            GroupExpenseSerializer(expense).data,
            message="Expense created and split.",
            status=status.HTTP_201_CREATED,
        )


class GroupExpenseDetailView(GroupAccessMixin, APIView):
    @extend_schema(
        operation_id="group_expense_retrieve",
        responses=OpenApiTypes.OBJECT,
        summary="Retrieve a shared expense with its shares",
    )
    def get(self, request, group_pk, expense_pk):
        group = self.get_group()
        expense = get_object_or_404(GroupExpense, pk=expense_pk, group=group)
        return api_success(GroupExpenseSerializer(expense).data)

    @extend_schema(
        operation_id="group_expense_delete",
        responses=OpenApiTypes.OBJECT,
        summary="Delete a shared expense",
    )
    def delete(self, request, group_pk, expense_pk):
        group = self.get_group()
        expense = get_object_or_404(GroupExpense, pk=expense_pk, group=group)
        if expense.paid_by_id != request.user.pk and not group.is_admin(request.user):
            raise PermissionDenied("Only the payer or an admin can delete this expense.")
        expense.delete()
        return api_success(message="Expense deleted.")


class SettlementsView(GroupAccessMixin, APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT, summary="List recorded settlements")
    def get(self, request, group_pk):
        group = self.get_group()
        settlements = group.settlements.select_related("from_user", "to_user").all()
        return api_success(SettlementSerializer(settlements, many=True).data)

    @extend_schema(
        request=SettlementCreateSerializer,
        responses=OpenApiTypes.OBJECT,
        summary="Record a settlement payment",
    )
    def post(self, request, group_pk):
        group = self.get_group()
        serializer = SettlementCreateSerializer(
            data=request.data, context={"group": group, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        settlement = serializer.save()
        return api_success(
            SettlementSerializer(settlement).data,
            message="Settlement recorded.",
            status=status.HTTP_201_CREATED,
        )
