from django.contrib import admin
from .models import Organization, Branch, Department


admin.site.register(Organization)
admin.site.register(Department)
admin.site.register(Branch)


