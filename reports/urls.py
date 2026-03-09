from django.urls import path
from . import views

urlpatterns = [
    path("", views.finance_report, name="finance_report"),
    path("processes/", views.process_report, name="process_report"),
    path("purchases/", views.purchase_report, name="purchase_report"),
    path("inventory/", views.inventory_report, name="inventory_report"),
    path("tasks/", views.task_report, name="task_report"),

]
