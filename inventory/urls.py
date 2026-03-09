from django.urls import path
from .views import inventory_item_list

urlpatterns = [
    path("", inventory_item_list, name="inventory_item_list"),
]
