from django.urls import path
from .views import dashboard_view, monitoring_view

urlpatterns = [
    path("dashboard/", dashboard_view, name="dashboard"),
    path("", monitoring_view, name="monitoring_dashboard"),
]
