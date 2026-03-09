from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from dashboard.services.monitoring import month_period, dashboard_kpis, problem_processes, time_analytics
from tasks.models import Task
from processes.models import ProcessInstance
from finance.models import Account, Transaction


def dashboard_view(request):
    user = request.user
    context = {}
    stats = {}

    # Общие метрики (для всех)
    stats["active_processes"] = ProcessInstance.objects.filter(is_completed=False).count()
    stats["total_profit"] = Transaction.objects.aggregate(total=Sum("amount"))["total"] or 0

    # === EMPLOYEE ===
    if user.role == "EMPLOYEE":
        context["role"] = "EMPLOYEE"

        qs_tasks = Task.objects.filter(
            assignee__user=user,
            status__in=["NEW", "IN_PROGRESS"],
        ).order_by("due_date")

        context["tasks"] = qs_tasks

        stats["my_tasks"] = qs_tasks.count()

        # Если у Task есть due_date
        today = timezone.now().date()
        stats["overdue_tasks"] = qs_tasks.filter(due_date__lt=today).count()

    # === MANAGER ===
    elif user.role == "MANAGER":
        context["role"] = "MANAGER"

        qs_pi = ProcessInstance.objects.filter(manager__user=user)
        context["process_instances"] = qs_pi

        stats["my_active_processes"] = qs_pi.filter(is_completed=False).count()

        stats["my_profit"] = (
            Transaction.objects
            .filter(process_instance__in=qs_pi)
            .aggregate(total=Sum("amount"))["total"]
            or 0
        )

    # === OWNER / ADMIN ===
    else:
        context["role"] = "OWNER"

        qs_pi = ProcessInstance.objects.all()
        context["process_instances"] = qs_pi

        context["accounts"] = Account.objects.all()
        stats["accounts_count"] = context["accounts"].count()

        stats["all_processes"] = qs_pi.count()
        stats["completed_processes"] = qs_pi.filter(is_completed=True).count()

        stats["income"] = (
            Transaction.objects.filter(amount__gt=0).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        stats["expense"] = (
            Transaction.objects.filter(amount__lt=0).aggregate(total=Sum("amount"))["total"]
            or 0
        )

    context["stats"] = stats
    return render(request, "dashboard/index.html", context)


def monitoring_view(request):
    today = timezone.now().date()
    period = month_period(today)

    context = {
        "role": request.user.role,
        "kpis": dashboard_kpis(request.user, period),
        "problems": problem_processes(request.user, period, limit=10),
        "analytics": time_analytics(request.user, period),
    }
    return render(request, "dashboard/monitoring.html", context)