from django.contrib import admin

from .models import ExpenseShare, Group, GroupExpense, GroupMember, Settlement


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "currency", "created_at")
    search_fields = ("name",)


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "role")


@admin.register(GroupExpense)
class GroupExpenseAdmin(admin.ModelAdmin):
    list_display = ("description", "group", "paid_by", "amount", "split_type")


@admin.register(ExpenseShare)
class ExpenseShareAdmin(admin.ModelAdmin):
    list_display = ("expense", "user", "amount", "is_settled")


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ("group", "from_user", "to_user", "amount", "created_at")
