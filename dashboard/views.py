from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from dashboard.services.monitoring import month_period, dashboard_kpis, problem_processes, time_analytics
from tasks.models import Task
from processes.models import ProcessInstance
from finance.models import Account, Transaction


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