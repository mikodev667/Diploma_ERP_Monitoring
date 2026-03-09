from django.contrib import admin
from .models import InventoryItem, InventoryCategory


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "quantity",
        "unit",
        "cost_per_unit",
        "total_value_display",
        "is_active",
    )

    list_filter = ("category", "is_active")
    search_fields = ("name",)

    def total_value_display(self, obj):
        return obj.total_value()

    total_value_display.short_description = "Total value"

from .models import InventoryUsage


@admin.register(InventoryUsage)
class InventoryUsageAdmin(admin.ModelAdmin):
    list_display = (
        "task",
        "item",
        "quantity",
        "cost_display",
        "created_at",
    )

    list_filter = ("item",)
    search_fields = ("task__title", "item__name")

    def cost_display(self, obj):
        return obj.cost()

    cost_display.short_description = "Cost"

