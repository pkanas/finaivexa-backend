from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("description", "user", "type", "amount", "date", "category")
    list_filter = ("type", "date", "payment_method")
    search_fields = ("description", "notes")
    date_hierarchy = "date"
