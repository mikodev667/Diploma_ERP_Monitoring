from django.db import models, transaction as db_transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings


class InventoryCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    name = models.CharField(max_length=255)

    category = models.ForeignKey(
        InventoryCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    unit = models.CharField(
        max_length=50,
        help_text="pcs, kg, l, m², etc."
    )

    cost_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional, for cost calculation"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def total_value(self):
        if self.cost_per_unit is None:
            return None
        return self.quantity * self.cost_per_unit

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"


class InventoryUsage(models.Model):
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="inventory_usages",
    )

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="usages",
    )

    transaction = models.OneToOneField(
        "finance.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_usage",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    applied = models.BooleanField(
        default=False,
        help_text="Whether inventory was deducted"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def cost(self):
        if self.item.cost_per_unit is None:
            return None
        return self.quantity * self.item.cost_per_unit

    def clean(self):
        if not self.applied:
            if self.quantity <= 0:
                raise ValidationError("Quantity must be positive")

            if self.item.quantity < self.quantity:
                raise ValidationError(
                    f"Not enough inventory: available {self.item.quantity}"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None

        with db_transaction.atomic():
            if is_new and not self.applied:
                if self.item.quantity < self.quantity:
                    raise ValidationError(
                        f"Not enough inventory: available {self.item.quantity}"
                    )

                # списание
                self.item.quantity -= self.quantity
                self.item.save(update_fields=["quantity"])
                self.applied = True

                # финансы
                if self.item.cost_per_unit:
                    from finance.models import Transaction, Account, Category

                    amount = self.quantity * self.item.cost_per_unit

                    account = Account.objects.get(
                        name=settings.INVENTORY_EXPENSE_ACCOUNT_NAME
                    )
                    category = Category.objects.get(
                        name=settings.INVENTORY_EXPENSE_CATEGORY_NAME
                    )

                    tx = Transaction.objects.create(
                        account=account,
                        category=category,
                        amount=-amount,
                        date=timezone.now().date(),
                        task=self.task,
                        process_instance=self.task.process_instance,
                        comment=f"Inventory usage: {self.item.name}",
                    )

                    self.transaction = tx

            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with db_transaction.atomic():
            if self.applied:
                self.item.quantity += self.quantity
                self.item.save(update_fields=["quantity"])
                self.applied = False

            if self.transaction:
                self.transaction.delete()

            super().delete(*args, **kwargs)
