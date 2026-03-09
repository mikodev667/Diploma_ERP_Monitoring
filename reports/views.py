from django.shortcuts import render
from django.db.models import Sum
from finance.models import Transaction
from inventory.models import InventoryUsage, InventoryItem
from processes.models import ProcessInstance
from django.db import models
from purchases.models import PurchaseItem
from tasks.models import Task


def finance_report(request):
    qs = Transaction.objects.all()

    total_income = qs.filter(amount__gt=0).aggregate(
        total=Sum("amount")
    )["total"] or 0

    total_expense = qs.filter(amount__lt=0).aggregate(
        total=Sum("amount")
    )["total"] or 0

    context = {
        "total_income": total_income,
        "total_expense": total_expense,
        "profit": total_income + total_expense,
        "transactions": qs.order_by("-date")[:100],
    }
    return render(request, "reports/finance.html", context)


def task_report(request):
    tasks = (
        Task.objects
        .select_related("process_instance", "stage")
        .all()
    )

    report = []

    for task in tasks:
        inventory_cost = (
            InventoryUsage.objects
            .filter(task=task)
            .aggregate(total=Sum("quantity"))
        )["total"] or 0

        finance_sum = (
            Transaction.objects
            .filter(task=task)
            .aggregate(total=Sum("amount"))
        )["total"] or 0

        report.append({
            "task": task,
            "process_instance": task.process_instance,
            "stage": task.stage,
            "inventory_cost": inventory_cost,
            "finance_result": finance_sum,
        })

    return render(
        request,
        "reports/tasks.html",
        {"report": report},
    )


def process_report(request):
    processes = (
        ProcessInstance.objects
        .select_related("process", "manager")
        .all()
    )

    report = []

    for pi in processes:
        income = (
            Transaction.objects
            .filter(process_instance=pi, amount__gt=0)
            .aggregate(total=Sum("amount"))
            .get("total")
        ) or 0

        expense = (
            Transaction.objects
            .filter(process_instance=pi, amount__lt=0)
            .aggregate(total=Sum("amount"))
            .get("total")
        ) or 0

        inventory_cost = 0
        usages = InventoryUsage.objects.filter(
            task__process_instance=pi
        )

        for usage in usages:
            cost = usage.cost()
            if cost:
                inventory_cost += cost

        report.append({
            "process_instance": pi,
            "process": pi.process,
            "manager": pi.manager,
            "income": income,
            "expense": expense,
            "profit": income + expense,
            "inventory_cost": inventory_cost,
            "is_completed": pi.is_completed,
        })

    return render(
        request,
        "reports/processes.html",
        {"report": report},
    )


def inventory_report(request):
    items = (
        InventoryItem.objects
        .select_related("category")
        .all()
    )

    report = []

    for item in items:
        used_quantity = (
            InventoryUsage.objects
            .filter(item=item)
            .aggregate(total=Sum("quantity"))
            .get("total")
        ) or 0

        total_value = None
        if item.cost_per_unit is not None:
            total_value = item.quantity * item.cost_per_unit

        report.append({
            "item": item,
            "category": item.category,
            "quantity": item.quantity,
            "unit": item.unit,
            "cost_per_unit": item.cost_per_unit,
            "used_quantity": used_quantity,
            "total_value": total_value,
            "is_active": item.is_active,
        })

    return render(
        request,
        "reports/inventory.html",
        {"report": report},
    )


def purchase_report(request):
    items = (
        PurchaseItem.objects
        .select_related(
            "purchase",
            "purchase__supplier",
            "item",
        )
        .all()
        .order_by("-purchase__date")
    )

    total_sum = (
        items.aggregate(
            total=Sum(
                models.F("quantity") * models.F("price_per_unit")
            )
        )["total"] or 0
    )

    report = []

    for pi in items:
        report.append({
            "date": pi.purchase.date,
            "supplier": pi.purchase.supplier,
            "item": pi.item,
            "quantity": pi.quantity,
            "price_per_unit": pi.price_per_unit,
            "total": pi.total_cost(),
            "applied": pi.applied,
        })

    return render(
        request,
        "reports/purchases.html",
        {
            "report": report,
            "total_sum": total_sum,
        },
    )