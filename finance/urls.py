from django.urls import path

from finance import views
from .views import account_list, transaction_list

urlpatterns = [
    path("", views.finance_dashboard, name="finance_dashboard"),
    path("account_list/", account_list, name="account_list"),
    path("transactions/", transaction_list, name="transaction_list"),
    path("accounts/<int:pk>/", views.account_detail, name="account_detail"),
]
