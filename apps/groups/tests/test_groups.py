from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.common.testing import BaseAPITestCase
from apps.groups.models import Group, GroupExpense, GroupMember
from apps.groups.services import GroupService

User = get_user_model()


class GroupTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.member2 = User.objects.create_user(email="m2@example.com", password="StrongPass123!")
        self.member3 = User.objects.create_user(email="m3@example.com", password="StrongPass123!")
        self.outsider = User.objects.create_user(email="out@example.com", password="StrongPass123!")
        self.group = GroupService.create_group(self.user, "Trip", currency="usd")

    def add_members(self):
        GroupService.add_member(self.group, self.member2)
        GroupService.add_member(self.group, self.member3)

    def test_create_group_makes_creator_admin(self):
        self.assertEqual(self.group.currency, "USD")
        self.assertEqual(self.group.members.count(), 1)
        self.assertTrue(self.group.is_admin(self.user))
        response = self.client.get(reverse("groups:group-list"))
        self.assertEqual(response.data["data"]["count"], 1)

    def test_add_member_via_api_requires_admin(self):
        self.client.force_authenticate(user=self.member2)
        GroupService.add_member(self.group, self.member2)
        response = self.client.post(
            reverse("groups:group-members", args=[self.group.pk]),
            {"email": "m3@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("groups:group-members", args=[self.group.pk]),
            {"email": "m3@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.group.is_member(self.member3))

    def test_equal_split_balances_and_settlement_plan(self):
        self.add_members()
        response = self.client.post(
            reverse("groups:group-expenses", args=[self.group.pk]),
            {
                "description": "Dinner",
                "amount": "100.00",
                "date": date.today().isoformat(),
                "paid_by": self.user.pk,
                "split_type": "equal",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expense = GroupExpense.objects.get(description="Dinner")
        shares = list(expense.shares.values_list("amount", flat=True))
        self.assertEqual(sum(shares), Decimal("100.00"))
        self.assertEqual(sorted(shares), [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")])

        balances = GroupService.balances(self.group)
        self.assertEqual(balances[self.user.pk], Decimal("66.66"))
        self.assertEqual(balances[self.member2.pk], Decimal("-33.33"))

        plan = GroupService.settlement_plan(self.group)
        self.assertEqual(len(plan), 2)
        self.assertEqual(
            sum((item["amount"] for item in plan), Decimal(0)), Decimal("66.66")
        )

    def test_percentage_and_custom_splits(self):
        self.add_members()
        percentage_expense = GroupService.create_expense(
            self.group, self.user, "Hotel", Decimal("200"), date.today(),
            split_type=GroupExpense.SplitType.PERCENTAGE,
            shares_data=[
                {"user_id": self.user.pk, "percentage": "50"},
                {"user_id": self.member2.pk, "percentage": "30"},
                {"user_id": self.member3.pk, "percentage": "20"},
            ],
        )
        self.assertEqual(
            list(percentage_expense.shares.values_list("amount", flat=True)),
            [Decimal("100.00"), Decimal("60.00"), Decimal("40.00")],
        )

        custom = GroupService.create_expense(
            self.group, self.member2, "Taxi", Decimal("90"), date.today(),
            split_type=GroupExpense.SplitType.CUSTOM,
            shares_data=[
                {"user_id": self.user.pk, "amount": "30"},
                {"user_id": self.member2.pk, "amount": "60"},
            ],
        )
        self.assertEqual(custom.shares.count(), 2)

    def test_invalid_split_rejected(self):
        self.add_members()
        with self.assertRaises(Exception):
            GroupService.create_expense(
                self.group, self.user, "Bad", Decimal("100"), date.today(),
                split_type=GroupExpense.SplitType.CUSTOM,
                shares_data=[{"user_id": self.user.pk, "amount": "10"}],
            )

    def test_settlement_updates_balances(self):
        self.add_members()
        GroupService.create_expense(
            self.group, self.user, "Dinner", Decimal("60"), date.today()
        )
        self.client.force_authenticate(user=self.member2)
        settlement = self.client.post(
            reverse("groups:group-settlements", args=[self.group.pk]),
            {
                "to_user": self.user.pk,
                "amount": "20.00",
                "note": "partial",
            },
            format="json",
        )
        self.assertEqual(settlement.status_code, status.HTTP_201_CREATED)
        balances = GroupService.balances(self.group)
        self.assertEqual(balances[self.member2.pk], Decimal("0.00"))

    def test_non_member_cannot_access_group(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(reverse("groups:group-list"))
        self.assertEqual(response.data["data"]["count"], 0)
        denied = self.client.get(
            reverse("groups:group-members", args=[self.group.pk])
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
