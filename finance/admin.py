from django.contrib import admin
from .models import Account, Category, Counterparty, Transaction


admin.site.register(Category)
admin.site.register(Counterparty)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    exclude = ("process_instance",)

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "currency", "current_balance")

    def current_balance(self, obj):
        return obj.balance()

    current_balance.short_description = "Balance"