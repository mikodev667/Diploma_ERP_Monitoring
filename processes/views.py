from django.shortcuts import render, get_object_or_404
from .models import ProcessInstance
from tasks.models import Task
from finance.models import Transaction
from django.utils import timezone
from processes.services import (
    instance_stage_timeline,
    current_stage_age,
    avg_stage_time_for_process,
)


def process_instance_list(request):
    user = request.user

    if user.role == "MANAGER":
        process_instances = ProcessInstance.objects.filter(
            manager__user=user
        )
    else:
        process_instances = ProcessInstance.objects.all()

    return render(
        request,
        "processes/process_instance_list.html",
        {
            "process_instances": process_instances,
            "today":timezone.now().date()
        }
    )


def process_instance_detail(request, pk):
    process_instance = get_object_or_404(ProcessInstance, pk=pk)

    tasks = (
        Task.objects
        .filter(process_instance=process_instance)
        .select_related("stage", "assignee")
    )
    transactions = (
        Transaction.objects
        .filter(process_instance=process_instance)
        .select_related("category", "account", "task")
        .order_by("-date")
    )

    # KPI по этапам
    stage_timeline = instance_stage_timeline(process_instance.id)
    stage_age = current_stage_age(process_instance.id)
    avg_stages = avg_stage_time_for_process(process_instance.process_id)

    # KPI summary (ВАЖНО: посчитать один раз)
    profit_value = process_instance.profit()       # метод
    is_overdue_value = process_instance.is_overdue()  # метод

    return render(
        request,
        "processes/process_instance_detail.html",
        {
            "process_instance": process_instance,
            "tasks": tasks,
            "transactions": transactions,
            "stage_timeline": stage_timeline,
            "stage_age": stage_age,
            "avg_stages": avg_stages,
            "profit_value": profit_value,
            "is_overdue_value": is_overdue_value,
            "today": timezone.now().date(),
            "now": timezone.now(),
        }
    )

