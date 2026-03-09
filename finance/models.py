from decimal import Decimal

from django.db import models
from django.db.models import Sum

from tasks.models import Task
from processes.models import ProcessInstance


class Account(models.Model):
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=3, default="KZT")

    def balance(self):
        income = self.transactions.filter(
            category__type="INCOME"
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        expense = self.transactions.filter(
            category__type="EXPENSE"
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return income - expense

    def __str__(self):
        return f"{self.name} ({self.currency})"



class Category(models.Model):
    TYPE_CHOICES = (
        ("INCOME", "Income"),
        ("EXPENSE", "Expense"),
    )

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    def __str__(self):
        return f"{self.name} [{self.type}]"


class Counterparty(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name



class Transaction(models.Model):
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    counterparty = models.ForeignKey(
        Counterparty,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )

    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    # ⚠️ Пользователь НЕ выбирает это поле вручную
    process_instance = models.ForeignKey(
        ProcessInstance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """
        Если выбрана задача — автоматически подтягиваем process_instance
        """
        if self.task and not self.process_instance:
            self.process_instance = self.task.process_instance
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.amount} — {self.category.name}"