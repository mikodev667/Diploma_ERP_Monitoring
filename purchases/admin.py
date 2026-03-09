from django.contrib import admin
from .models import Supplier, Purchase, PurchaseItem


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("id", "supplier", "date")
    list_filter = ("supplier", "date")


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = (
        "purchase",
        "item",
        "quantity",
        "price_per_unit",
        "applied",
    )
    list_filter = ("purchase", "item", "applied")
    readonly_fields = ("applied", "transaction")
