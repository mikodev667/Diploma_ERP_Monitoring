from django.shortcuts import render, redirect
from .models import InventoryItem


def inventory_item_list(request):
    if request.user.role == "EMPLOYEE":
        items = InventoryItem.objects.filter(is_active=True)
    else:
        items = InventoryItem.objects.all()

    return render(
        request,
        "inventory/item_list.html",
        {
            "items": items,
        }
    )
