from django.urls import path
from .views import monitoring_view, main_page

urlpatterns = [
    path("", main_page, name="main_page"),
    path("dashboard", monitoring_view, name="monitoring_dashboard"),
]
