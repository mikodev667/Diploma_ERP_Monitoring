from django.contrib import admin
from people.models import Employee
from .models import Process, Stage, ProcessInstance


class StageInline(admin.TabularInline):
    model = Stage
    extra = 1


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_active")
    list_filter = ("organization", "is_active")
    inlines = [StageInline]


admin.site.register(Stage)


@admin.register(ProcessInstance)
class ProcessInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "process",
        "manager",
        "started_at",
        "current_profit",
        "is_completed",
    )

    list_filter = ("process", "manager", "is_completed")

    def current_profit(self, obj):
        return obj.profit()

    current_profit.short_description = "Profit"
    current_profit.admin_order_field = "id"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "manager":
            kwargs["queryset"] = Employee.objects.filter(
                user__role="MANAGER"
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)