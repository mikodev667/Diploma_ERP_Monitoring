from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Branch(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches",
    )
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.organization.name} — {self.name}"


class Department(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="departments",
    )
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.branch.name} — {self.name}"
