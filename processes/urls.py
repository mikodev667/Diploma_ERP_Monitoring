from django.urls import path
from .views import process_instance_detail, process_instance_list

urlpatterns = [
    path("", process_instance_list, name="process_instance_list"),
    path("instances/<int:pk>/", process_instance_detail, name="process_instance_detail"),
]
