from django.contrib import admin
from .forms import TaskAdminForm
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm
    list_display = ("title", "process_instance", "stage", "assignee", "status")