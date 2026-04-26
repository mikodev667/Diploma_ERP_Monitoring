from decimal import Decimal

from django.db import models
from django.db.models import Sum, Max
from django.utils import timezone

from orgs.models import Organization, Branch


class Process(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="processes",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Stage(models.Model):
    process = models.ForeignKey(
        Process,
        on_delete=models.CASCADE,
        related_name="stages",
    )
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        unique_together = ("process", "order")

    def __str__(self):
        return f"{self.process.name} — {self.name}"


class StageHistory(models.Model):
    process_instance = models.ForeignKey(
        "ProcessInstance",
        on_delete=models.CASCADE,
        related_name="stage_history",
    )
    stage = models.ForeignKey(
        "Stage",
        on_delete=models.PROTECT,
        related_name="history_rows",
    )

    entered_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["process_instance", "stage"]),
            models.Index(fields=["stage", "entered_at"]),
            models.Index(fields=["left_at"]),
        ]

    def duration(self):
        end = self.left_at or timezone.now()
        return end - self.entered_at


class ProcessInstance(models.Model):
    process = models.ForeignKey(
        Process,
        on_delete=models.CASCADE,
        related_name="instances",
    )
    name = models.CharField(max_length=255)

    manager = models.ForeignKey(
        "people.Employee",   # ← строка
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_processes",
    )
    planned_budget = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True
    )
    planned_end_date = models.DateField(
        null=True, blank=True
    )
    started_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)

    current_stage = models.ForeignKey(
        "Stage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_instances",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="process_instances",
    )

    business_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Business date",
    )

    def inventory_cost(self):
        from inventory.models import InventoryUsage

        total = Decimal("0")
        usages = InventoryUsage.objects.filter(
            task__process_instance=self
        )

        for usage in usages:
            cost = usage.cost()
            if cost:
                total += cost

        return total

    def profit(self):
        """
        Real profit of process instance based on transactions.
        Inventory costs are included via expense transactions.
        """
        from finance.models import Transaction  # ← локальный импорт

        total = (
            Transaction.objects
            .filter(process_instance=self)
            .aggregate(total=Sum("amount"))
            .get("total")
        )
        return total or Decimal("0")

    def duration(self):
        """
        Фактическая длительность процесса.
        Не трогаем completed_at, но используем его, если он вдруг заполнен.
        Иначе:
          - если процесс завершён и у задач есть completed_at -> берём max
          - иначе -> now() - started_at
        """
        if getattr(self, "completed_at", None):
            end = self.completed_at
        else:
            end = None
            if self.is_completed:
                end = (
                    self.tasks.filter(status="DONE", completed_at__isnull=False)
                    .aggregate(mx=Max("completed_at"))["mx"]
                )
            end = end or timezone.now()

        return end - self.started_at

    def progress(self, exclude_canceled=True):
        qs = self.tasks.all()
        if exclude_canceled:
            qs = qs.exclude(status="CANCELED")

        total = qs.count()
        if total == 0:
            return Decimal("0")

        done = qs.filter(status="DONE").count()
        return (Decimal(done) / Decimal(total)) * Decimal("100")

    def cost(self):
        """
        Расходы: суммы отрицательных транзакций (в абсолюте).
        Инвентарь уже попадает сюда, потому что InventoryUsage создаёт Transaction с минусом.
        """
        from finance.models import Transaction

        s = (
                Transaction.objects
                .filter(process_instance=self, amount__lt=0)
                .aggregate(total=Sum("amount"))["total"]
            ) or Decimal("0")
        return abs(s)

    def revenue(self):
        """Доходы: суммы положительных транзакций."""
        from finance.models import Transaction

        s = (
                Transaction.objects
                .filter(process_instance=self, amount__gt=0)
                .aggregate(total=Sum("amount"))["total"]
            ) or Decimal("0")
        return s

    def plan_fact_budget_delta(self):
        """
        План-факт по бюджету:
        + значение -> перерасход (fact_cost - planned_budget)
        None -> если план не задан
        """
        if self.planned_budget is None:
            return None
        return self.cost() - self.planned_budget

    def is_budget_overrun(self):
        if self.planned_budget is None:
            return False
        return self.cost() > self.planned_budget

    def is_overdue(self):
        """
        Просрочка по плановой дате (если задана) и процесс ещё не завершён.
        """
        if not self.planned_end_date:
            return False
        return (timezone.now().date() > self.planned_end_date) and (not self.is_completed)

    def efficiency_score(self):
        """
        Простая итоговая оценка 0..100:
        - прогресс 0..50
        - срок 0..25 (если плана нет -> 12.5)
        - бюджет 0..25 (если плана нет -> 12.5)
        """
        score = Decimal("0")

        score += (self.progress(exclude_canceled=True) / Decimal("100")) * Decimal("50")

        if self.planned_end_date:
            score += Decimal("0") if self.is_overdue() else Decimal("25")
        else:
            score += Decimal("12.5")

        if self.planned_budget is None:
            score += Decimal("12.5")
        else:
            score += Decimal("0") if self.is_budget_overrun() else Decimal("25")

        if score < 0:
            return Decimal("0")
        if score > 100:
            return Decimal("100")
        return score


    def __str__(self):
        return self.name
