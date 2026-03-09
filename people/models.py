from django.conf import settings
from django.db import models

from orgs.models import Department


class Employee(models.Model):
    STATUS_CHOICES = (
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("FIRED", "Fired"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee",
    )

    full_name = models.CharField(max_length=255)
    position = models.CharField(max_length=100)
    hire_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="ACTIVE",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )

    def __str__(self):
        return self.full_name
