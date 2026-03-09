from django.db import models, transaction as db_transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings

from inventory.models import InventoryItem


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Purchase(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    date = models.DateField(default=timezone.now)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Purchase #{self.id} from {self.supplier}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name="items",
    )

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="purchase_items",
    )

    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    price_per_unit = models.DecimalField(max_digits=12, decimal_places=2)

    transaction = models.OneToOneField(
        "finance.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_item",
    )

    applied = models.BooleanField(default=False)

    def total_cost(self):
        return self.quantity * self.price_per_unit

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Quantity must be positive")
        if self.price_per_unit <= 0:
            raise ValidationError("Price per unit must be positive")

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None

        with db_transaction.atomic():
            if is_new and not self.applied:
                # 1) Приход на склад
                self.item.quantity += self.quantity
                self.item.save(update_fields=["quantity"])
                self.applied = True

                # 2) Финансы
                from finance.models import Transaction, Account, Category

                amount = self.total_cost()

                account = Account.objects.get(
                    name=settings.PURCHASE_EXPENSE_ACCOUNT_NAME
                )
                category = Category.objects.get(
                    name=settings.PURCHASE_EXPENSE_CATEGORY_NAME
                )

                tx = Transaction.objects.create(
                    account=account,
                    category=category,
                    amount=-amount,
                    date=self.purchase.date,
                    comment=f"Purchase: {self.item.name} from {self.purchase.supplier}",
                )

                self.transaction = tx

            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with db_transaction.atomic():
            if self.applied:
                self.item.quantity -= self.quantity
                self.item.save(update_fields=["quantity"])
                self.applied = False

            if self.transaction:
                self.transaction.delete()

            super().delete(*args, **kwargs)
