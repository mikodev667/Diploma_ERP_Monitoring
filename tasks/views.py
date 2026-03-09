from django.shortcuts import render

from tasks.models import Task


def task_list(request):
    user = request.user

    if user.role == "EMPLOYEE":
        tasks = Task.objects.filter(assignee__user=user)
    elif user.role == "MANAGER":
        tasks = Task.objects.filter(
            process_instance__manager__user=user
        )
    else:
        tasks = Task.objects.all()

    return render(
        request,
        "tasks/task_list.html",
        {
            "tasks": tasks,
        }
    )
