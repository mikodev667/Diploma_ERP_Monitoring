from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce, TruncDay
from django.utils import timezone

from tasks.models import Task
from processes.models import ProcessInstance
from finance.models import Transaction


@dataclass
class Period:
    start: date
    end: date  # inclusive


def month_period(ref: date) -> Period:
    start = ref.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    end = next_month - timedelta(days=1)
    return Period(start=start, end=end)


def prev_month_period(ref: date) -> Period:
    cur = month_period(ref)
    prev_end = cur.start - timedelta(days=1)
    return month_period(prev_end)


def scope_process_instances(user):
    """
    Возвращает queryset ProcessInstance согласно роли.
    CANCELED задачи в метриках исключаются отдельно.
    """
    role = getattr(user, "role", "OWNER")

    if role == "EMPLOYEE":
        # процессы, где есть задачи сотрудника
        return ProcessInstance.objects.filter(tasks__assignee__user=user).distinct()

    if role == "MANAGER":
        return ProcessInstance.objects.filter(manager__user=user)

    # OWNER/ADMIN
    return ProcessInstance.objects.all()


def dashboard_kpis(user, period: Period):
    today = timezone.now().date()

    qs_pi = scope_process_instances(user)

    # Active processes
    active_processes = qs_pi.filter(is_completed=False).count()

    # Overdue tasks (exclude DONE/CANCELED)
    overdue_tasks = (
        Task.objects.filter(
            process_instance__in=qs_pi,
            due_date__isnull=False,
            due_date__lt=today,
        )
        .exclude(status__in=["DONE", "CANCELED"])
        .count()
    )

    # Финансовые суммы за период (на уровне системы/скоупа пользователя)
    tx = Transaction.objects.filter(
        process_instance__in=qs_pi,
        date__gte=period.start,
        date__lte=period.end,
    )

    income = tx.filter(amount__gt=0).aggregate(
        s=Coalesce(Sum("amount"), Decimal("0"))
    )["s"]

    expense_neg = tx.filter(amount__lt=0).aggregate(
        s=Coalesce(Sum("amount"), Decimal("0"))
    )["s"]  # отрицательное

    profit = tx.aggregate(
        s=Coalesce(Sum("amount"), Decimal("0"))
    )["s"]

    expense = abs(expense_neg)

    # Avg profit per process (за период)
    profit_rows = (
        tx.values("process_instance_id")
        .annotate(p=Coalesce(Sum("amount"), Decimal("0")))
        .values_list("p", flat=True)
    )
    profits = list(profit_rows)  # <-- без ["p"]

    if profits:
        avg_profit = (sum(profits) / Decimal(len(profits))).quantize(Decimal("0.01"))
    else:
        avg_profit = Decimal("0.00")
    # Budget overruns (за период)
    # cost per process за период (abs negative)
    cost_rows = (
        tx.filter(amount__lt=0)
        .values("process_instance_id")
        .annotate(cost=Coalesce(Sum("amount"), Decimal("0")))
    )
    cost_map = {r["process_instance_id"]: abs(r["cost"]) for r in cost_rows}

    planned_rows = qs_pi.filter(planned_budget__isnull=False).values("id", "planned_budget")
    budget_overruns = 0
    for r in planned_rows:
        if cost_map.get(r["id"], Decimal("0")) > r["planned_budget"]:
            budget_overruns += 1

    return {
        "active_processes": active_processes,
        "avg_profit": avg_profit,
        "overdue_tasks": overdue_tasks,
        "budget_overruns": budget_overruns,
        "income": income,
        "expense": expense,
        "profit": profit,
        "period": period,
    }


def problem_processes(user, period: Period, limit=10):
    """
    Проблемные процессы за период:
    - negative profit
    - budget overrun (если planned_budget задан)
    - overdue (planned_end_date < today, is_completed=False)
    """
    today = timezone.now().date()
    qs_pi = scope_process_instances(user)

    tx = Transaction.objects.filter(
        process_instance__in=qs_pi,
        date__gte=period.start,
        date__lte=period.end,
    )

    agg = (
        tx.values("process_instance_id")
        .annotate(
            profit=Coalesce(Sum("amount"), Decimal("0")),
            cost=Coalesce(Sum("amount", filter=Q(amount__lt=0)), Decimal("0")),  # отрицательное
        )
    )
    agg_map = {r["process_instance_id"]: r for r in agg}

    items = []
    for pi in qs_pi.select_related("process", "manager"):
        a = agg_map.get(pi.id, {"profit": Decimal("0"), "cost": Decimal("0")})
        profit = a["profit"]
        cost = abs(a["cost"])

        flags = []
        if profit < 0:
            flags.append("NEGATIVE_PROFIT")

        if pi.planned_budget is not None and cost > pi.planned_budget:
            flags.append("BUDGET_OVERRUN")

        if pi.planned_end_date and (today > pi.planned_end_date) and (not pi.is_completed):
            flags.append("OVERDUE")

        if flags:
            items.append({
                "process_instance": pi,
                "profit": profit,
                "cost": cost,
                "flags": flags,
            })

    # сортируем: сначала с NEGATIVE_PROFIT, затем BUDGET_OVERRUN, затем OVERDUE
    def rank(x):
        f = x["flags"]
        return (
            0 if "NEGATIVE_PROFIT" in f else 1,
            0 if "BUDGET_OVERRUN" in f else 1,
            0 if "OVERDUE" in f else 1,
        )

    items.sort(key=rank)
    return items[:limit]


def time_analytics(user, period: Period):
    qs_pi = scope_process_instances(user)
    prev = prev_month_period(period.start)

    def sums(p: Period):
        tx = Transaction.objects.filter(
            process_instance__in=qs_pi,
            date__gte=p.start, date__lte=p.end
        )
        income = tx.filter(amount__gt=0).aggregate(s=Coalesce(Sum("amount"), Decimal("0")))["s"]
        expense_neg = tx.filter(amount__lt=0).aggregate(s=Coalesce(Sum("amount"), Decimal("0")))["s"]
        profit = tx.aggregate(s=Coalesce(Sum("amount"), Decimal("0")))["s"]
        return {"income": income, "expense": abs(expense_neg), "profit": profit}

    current = sums(period)
    previous = sums(prev)

    daily_profit = (
        Transaction.objects.filter(
            process_instance__in=qs_pi,
            date__gte=period.start, date__lte=period.end
        )
        .annotate(d=TruncDay("date"))
        .values("d")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0")))
        .order_by("d")
    )

    return {
        "current": current,
        "previous": previous,
        "daily_profit": list(daily_profit),
        "current_period": period,
        "previous_period": prev,
    }
