"""Group, split and settlement business logic."""
from decimal import Decimal

from django.db import transaction

from apps.common.exceptions import ServiceError
from apps.common.utils import to_money

from .models import ExpenseShare, Group, GroupExpense, GroupMember, Settlement


class GroupService:
    @staticmethod
    @transaction.atomic
    def create_group(user, name, description="", currency="USD"):
        group = Group.objects.create(
            name=name.strip(),
            description=description,
            currency=currency.upper(),
            created_by=user,
        )
        GroupMember.objects.create(
            group=group, user=user, role=GroupMember.Role.ADMIN
        )
        return group

    @staticmethod
    def add_member(group, user, role=GroupMember.Role.MEMBER):
        member, created = GroupMember.objects.get_or_create(
            group=group, user=user, defaults={"role": role}
        )
        return member, created

    @staticmethod
    @transaction.atomic
    def create_expense(
        group,
        paid_by,
        description,
        amount,
        date,
        split_type=GroupExpense.SplitType.EQUAL,
        shares_data=None,
        category=None,
    ):
        """Create a group expense and its shares with exact total allocation."""
        if not group.is_member(paid_by):
            raise ServiceError("The payer must be a member of the group.")

        member_ids = list(group.members.order_by("pk").values_list("pk", flat=True))
        if not member_ids:
            raise ServiceError("The group has no members.")

        amount = to_money(amount)
        if amount <= 0:
            raise ServiceError("Amount must be greater than zero.")

        shares = []
        if split_type == GroupExpense.SplitType.EQUAL:
            base = to_money(amount / len(member_ids))
            remainder = to_money(amount - base * len(member_ids))
            for index, user_id in enumerate(member_ids):
                shares.append(
                    {
                        "user_id": user_id,
                        "amount": base + (remainder if index == 0 else Decimal(0)),
                        "percentage": None,
                    }
                )

        elif split_type == GroupExpense.SplitType.CUSTOM:
            if not shares_data:
                raise ServiceError("Custom splits require share amounts.")
            shares, seen = [], set()
            for item in shares_data:
                user_id = item["user_id"]
                if user_id not in member_ids:
                    raise ServiceError("Share users must be group members.")
                if user_id in seen:
                    raise ServiceError("A member cannot appear twice in a split.")
                seen.add(user_id)
                shares.append({"user_id": user_id, "amount": to_money(item["amount"]), "percentage": None})
            if sum((s["amount"] for s in shares), Decimal(0)) != amount:
                raise ServiceError("Custom share amounts must add up to the total amount.")

        elif split_type == GroupExpense.SplitType.PERCENTAGE:
            if not shares_data:
                raise ServiceError("Percentage splits require share percentages.")
            shares, seen = [], set()
            for item in shares_data:
                user_id = item["user_id"]
                if user_id not in member_ids:
                    raise ServiceError("Share users must be group members.")
                if user_id in seen:
                    raise ServiceError("A member cannot appear twice in a split.")
                seen.add(user_id)
                percentage = Decimal(str(item["percentage"]))
                shares.append(
                    {
                        "user_id": user_id,
                        "amount": to_money(amount * percentage / 100),
                        "percentage": percentage,
                    }
                )
            if sum((Decimal(str(s["percentage"])) for s in shares), Decimal(0)) != 100:
                raise ServiceError("Percentages must add up to 100.")
            allocated = sum((s["amount"] for s in shares), Decimal(0))
            shares[0]["amount"] = to_money(shares[0]["amount"] + (amount - allocated))

        else:
            raise ServiceError("Unknown split type.")

        expense = GroupExpense.objects.create(
            group=group,
            paid_by=paid_by,
            description=description,
            amount=amount,
            date=date,
            category=category,
            split_type=split_type,
        )
        ExpenseShare.objects.bulk_create(
            [ExpenseShare(expense=expense, **share) for share in shares]
        )
        return expense

    @staticmethod
    def balances(group):
        """Net balance per member. Positive = owed to them, negative = they owe."""
        balances = {member.user_id: Decimal(0) for member in group.memberships.all()}
        for expense in group.expenses.all():
            for share in expense.shares.all():
                balances.setdefault(expense.paid_by_id, Decimal(0))
                balances[expense.paid_by_id] += share.amount
                balances[share.user_id] -= share.amount
        for settlement in group.settlements.all():
            balances.setdefault(settlement.from_user_id, Decimal(0))
            balances.setdefault(settlement.to_user_id, Decimal(0))
            balances[settlement.from_user_id] += settlement.amount
            balances[settlement.to_user_id] -= settlement.amount
        return {uid: to_money(value) for uid, value in balances.items()}

    @staticmethod
    def settlement_plan(group):
        """Greedy creditor/debtor matching that minimises the number of payments."""
        balances = GroupService.balances(group)
        debtors = [
            {"user_id": uid, "amount": -amount}
            for uid, amount in balances.items()
            if amount < 0
        ]
        creditors = [
            {"user_id": uid, "amount": amount}
            for uid, amount in balances.items()
            if amount > 0
        ]
        debtors.sort(key=lambda x: x["amount"], reverse=True)
        creditors.sort(key=lambda x: x["amount"], reverse=True)

        plan = []
        di = ci = 0
        while di < len(debtors) and ci < len(creditors):
            pay = min(debtors[di]["amount"], creditors[ci]["amount"])
            plan.append(
                {
                    "from_user_id": debtors[di]["user_id"],
                    "to_user_id": creditors[ci]["user_id"],
                    "amount": to_money(pay),
                }
            )
            debtors[di]["amount"] -= pay
            creditors[ci]["amount"] -= pay
            if debtors[di]["amount"] == 0:
                di += 1
            if creditors[ci]["amount"] == 0:
                ci += 1
        return plan

    @staticmethod
    @transaction.atomic
    def create_settlement(group, from_user, to_user, amount, note=""):
        if from_user.pk == to_user.pk:
            raise ServiceError("A settlement must involve two different members.")
        if not (group.is_member(from_user) and group.is_member(to_user)):
            raise ServiceError("Both users must be members of the group.")
        return Settlement.objects.create(
            group=group, from_user=from_user, to_user=to_user, amount=amount, note=note
        )
