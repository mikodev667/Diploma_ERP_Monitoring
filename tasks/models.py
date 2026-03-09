from django.db import models
from people.models import Employee
from processes.models import Stage


class Task(models.Model):
    STATUS_CHOICES = (
        ("NEW", "New"),
        ("IN_PROGRESS", "In Progress"),
        ("BLOCKED", "Blocked"),
        ("DONE", "Done"),
        ("CANCELED", "Canceled"),
    )

    planned_hours = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True
    )

    process_instance = models.ForeignKey(
        "processes.ProcessInstance",
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    stage = models.ForeignKey(
        Stage,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    assignee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="NEW",
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Проверяем: все ли задачи процесса выполнены
        if self.process_instance:
            tasks = self.process_instance.tasks.all()
            if tasks.exists() and all(t.status == "DONE" for t in tasks):
                self.process_instance.is_completed = True
                self.process_instance.save()


    due_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


def inventory_cost(self):
    total = 0
    for usage in self.inventory_usages.all():
        cost = usage.cost()
        if cost:
            total += cost
    return total
