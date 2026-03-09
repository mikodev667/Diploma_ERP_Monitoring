from datetime import date

from django.db.models import Sum
from django.shortcuts import render, get_object_or_404
from .models import Account, Transaction


def account_list(request):
    return render(
        request,
        "finance/accounts.html",
        {
            "accounts": Account.objects.all(),
        }
    )

def transaction_list(request):
    user = request.user

    if user.role == "MANAGER":
        transactions = Transaction.objects.filter(
            process_instance__manager__user=user
        )
    else:
        transactions = Transaction.objects.all()

    return render(
        request,
        "finance/transactions.html",
        {
            "transactions": transactions,
        }
    )


def account_detail(request, pk):
    account = get_object_or_404(Account, pk=pk)

    transactions = (
        account.transactions
        .select_related("category", "process_instance", "task")
        .order_by("-date")
    )

    income = (
        transactions.filter(amount__gt=0)
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )

    expense = (
        transactions.filter(amount__lt=0)
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )

    context = {
        "account": account,
        "transactions": transactions[:100],  # не грузим всё сразу
        "income": income,
        "expense": expense,
        "balance": income + expense,
    }

    return render(request, "finance/account_detail.html", context)



def finance_dashboard(request):
    today = date.today()
    month_start = today.replace(day=1)

    transactions = Transaction.objects.all()

    total_balance = (
        transactions.aggregate(total=Sum("amount"))["total"]
        or 0
    )

    income_month = (
        transactions.filter(
            amount__gt=0,
            date__gte=month_start
        )
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )

    expense_month = (
        transactions.filter(
            amount__lt=0,
            date__gte=month_start
        )
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )

    accounts = Account.objects.all()

    last_transactions = (
        Transaction.objects
        .select_related("account", "category", "process_instance")
        .order_by("-date", "-id")[:15]
    )

    context = {
        "total_balance": total_balance,
        "income_month": income_month,
        "expense_month": expense_month,
        "net_month": income_month + expense_month,
        "accounts": accounts,
        "last_transactions": last_transactions,
    }

    return render(
        request,
        "finance/dashboard.html",
        context
    )