from decimal import Decimal
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from orgs.models import Organization, Branch, Department
from people.models import Employee

from processes.models import Process, Stage, ProcessInstance, StageHistory
from tasks.models import Task

from finance.models import Account, Category, Counterparty, Transaction
from inventory.models import InventoryCategory, InventoryItem, InventoryUsage
from purchases.models import Supplier, Purchase, PurchaseItem


class Command(BaseCommand):
    help = "Create demo data for business process efficiency monitoring"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing demo data before seeding",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.ensure_settings()

        if options["clear"]:
            self.clear_data()

        users = self.create_users()
        org_data = self.create_organization()
        employees = self.create_employees(users, org_data)
        finance_data = self.create_finance()
        inventory_data = self.create_inventory()
        purchase_data = self.create_purchases(inventory_data)
        processes_data = self.create_processes(org_data, employees)
        instances = self.create_process_instances(processes_data, org_data, employees)
        tasks = self.create_tasks(instances, employees)
        self.create_transactions(finance_data, instances, tasks)
        self.create_inventory_usages(inventory_data, tasks)
        self.create_stage_history(instances)

        self.stdout.write(
            self.style.SUCCESS("Demo data successfully created.")
        )

        self.stdout.write("")
        self.stdout.write("Users:")
        self.stdout.write("admin / admin12345")
        self.stdout.write("manager / manager12345")
        self.stdout.write("employee / employee12345")
        self.stdout.write("employee2 / employee12345")

    def ensure_settings(self):
        """
        InventoryUsage and PurchaseItem use settings names.
        If these constants are missing in settings.py, we create them temporarily.
        """

        defaults = {
            "INVENTORY_EXPENSE_ACCOUNT_NAME": "Main Cashbox",
            "INVENTORY_EXPENSE_CATEGORY_NAME": "Inventory usage",
            "PURCHASE_EXPENSE_ACCOUNT_NAME": "Main Cashbox",
            "PURCHASE_EXPENSE_CATEGORY_NAME": "Purchase expense",
        }

        for name, value in defaults.items():
            if not hasattr(settings, name):
                setattr(settings, name, value)

    def clear_data(self):
        """
        Delete demo data in safe order.
        """

        PurchaseItem.objects.all().delete()
        Purchase.objects.all().delete()
        Supplier.objects.all().delete()

        InventoryUsage.objects.all().delete()
        Transaction.objects.all().delete()

        InventoryItem.objects.all().delete()
        InventoryCategory.objects.all().delete()

        Account.objects.all().delete()
        Category.objects.all().delete()
        Counterparty.objects.all().delete()

        StageHistory.objects.all().delete()
        Task.objects.all().delete()
        ProcessInstance.objects.all().delete()
        Stage.objects.all().delete()
        Process.objects.all().delete()

        Employee.objects.all().delete()
        Department.objects.all().delete()
        Branch.objects.all().delete()
        Organization.objects.all().delete()

        User = get_user_model()
        User.objects.filter(
            username__in=["admin", "manager", "employee", "employee2"]
        ).delete()

        self.stdout.write(self.style.WARNING("Old demo data deleted."))

    def create_users(self):
        User = get_user_model()

        admin = User.objects.create_user(
            username="admin",
            password="admin12345",
            email="admin@example.com",
            first_name="System",
            last_name="Admin",
            role="ADMIN",
            is_staff=True,
            is_superuser=True,
        )

        manager = User.objects.create_user(
            username="manager",
            password="manager12345",
            email="manager@example.com",
            first_name="Ayan",
            last_name="Manager",
            role="MANAGER",
            is_staff=True,
        )

        employee = User.objects.create_user(
            username="employee",
            password="employee12345",
            email="employee@example.com",
            first_name="Miras",
            last_name="Employee",
            role="EMPLOYEE",
        )

        employee2 = User.objects.create_user(
            username="employee2",
            password="employee12345",
            email="employee2@example.com",
            first_name="Dana",
            last_name="Employee",
            role="EMPLOYEE",
        )

        return {
            "admin": admin,
            "manager": manager,
            "employee": employee,
            "employee2": employee2,
        }

    def create_organization(self):
        org = Organization.objects.create(
            name="Demo Business Group"
        )

        branch_main = Branch.objects.create(
            organization=org,
            name="Almaty Main Branch",
        )

        branch_second = Branch.objects.create(
            organization=org,
            name="Astana Branch",
        )

        dep_operations = Department.objects.create(
            branch=branch_main,
            name="Operations Department",
        )

        dep_sales = Department.objects.create(
            branch=branch_main,
            name="Sales Department",
        )

        dep_warehouse = Department.objects.create(
            branch=branch_second,
            name="Warehouse Department",
        )

        return {
            "org": org,
            "branch_main": branch_main,
            "branch_second": branch_second,
            "dep_operations": dep_operations,
            "dep_sales": dep_sales,
            "dep_warehouse": dep_warehouse,
        }

    def create_employees(self, users, org_data):
        today = timezone.now().date()

        admin_employee = Employee.objects.create(
            user=users["admin"],
            full_name="System Admin",
            position="Administrator",
            hire_date=today - timedelta(days=700),
            status="ACTIVE",
            department=org_data["dep_operations"],
        )

        manager_employee = Employee.objects.create(
            user=users["manager"],
            full_name="Ayan Manager",
            position="Business Process Manager",
            hire_date=today - timedelta(days=500),
            status="ACTIVE",
            department=org_data["dep_operations"],
        )

        employee = Employee.objects.create(
            user=users["employee"],
            full_name="Miras Employee",
            position="Process Specialist",
            hire_date=today - timedelta(days=250),
            status="ACTIVE",
            department=org_data["dep_sales"],
        )

        employee2 = Employee.objects.create(
            user=users["employee2"],
            full_name="Dana Employee",
            position="Warehouse Specialist",
            hire_date=today - timedelta(days=180),
            status="ACTIVE",
            department=org_data["dep_warehouse"],
        )

        return {
            "admin": admin_employee,
            "manager": manager_employee,
            "employee": employee,
            "employee2": employee2,
        }

    def create_finance(self):
        purchase_account, _ = Account.objects.get_or_create(
            name=settings.PURCHASE_EXPENSE_ACCOUNT_NAME,
            defaults={"currency": "KZT"},
        )

        inventory_account, _ = Account.objects.get_or_create(
            name=settings.INVENTORY_EXPENSE_ACCOUNT_NAME,
            defaults={"currency": "KZT"},
        )

        bank, _ = Account.objects.get_or_create(
            name="Bank Account",
            defaults={"currency": "KZT"},
        )

        income_category, _ = Category.objects.get_or_create(
            name="Sales income",
            type="INCOME",
        )

        service_income, _ = Category.objects.get_or_create(
            name="Service income",
            type="INCOME",
        )

        inventory_expense, _ = Category.objects.get_or_create(
            name=settings.INVENTORY_EXPENSE_CATEGORY_NAME,
            type="EXPENSE",
        )

        purchase_expense, _ = Category.objects.get_or_create(
            name=settings.PURCHASE_EXPENSE_CATEGORY_NAME,
            type="EXPENSE",
        )

        salary_expense, _ = Category.objects.get_or_create(
            name="Salary expense",
            type="EXPENSE",
        )

        logistics_expense, _ = Category.objects.get_or_create(
            name="Logistics expense",
            type="EXPENSE",
        )

        customer, _ = Counterparty.objects.get_or_create(
            name="Demo Customer LLP",
        )

        supplier, _ = Counterparty.objects.get_or_create(
            name="Demo Supplier LLP",
        )

        return {
            "account": purchase_account,
            "inventory_account": inventory_account,
            "bank": bank,
            "income_category": income_category,
            "service_income": service_income,
            "inventory_expense": inventory_expense,
            "purchase_expense": purchase_expense,
            "salary_expense": salary_expense,
            "logistics_expense": logistics_expense,
            "customer": customer,
            "supplier": supplier,
        }

    def create_inventory(self):
        raw_materials = InventoryCategory.objects.create(
            name="Raw materials",
        )

        packaging = InventoryCategory.objects.create(
            name="Packaging",
        )

        equipment = InventoryCategory.objects.create(
            name="Equipment",
        )

        coffee = InventoryItem.objects.create(
            name="Coffee beans",
            category=raw_materials,
            quantity=Decimal("80.00"),
            unit="kg",
            cost_per_unit=Decimal("4500.00"),
            is_active=True,
        )

        milk = InventoryItem.objects.create(
            name="Milk",
            category=raw_materials,
            quantity=Decimal("150.00"),
            unit="l",
            cost_per_unit=Decimal("650.00"),
            is_active=True,
        )

        cups = InventoryItem.objects.create(
            name="Paper cups",
            category=packaging,
            quantity=Decimal("2000.00"),
            unit="pcs",
            cost_per_unit=Decimal("35.00"),
            is_active=True,
        )

        boxes = InventoryItem.objects.create(
            name="Delivery boxes",
            category=packaging,
            quantity=Decimal("500.00"),
            unit="pcs",
            cost_per_unit=Decimal("120.00"),
            is_active=True,
        )

        grinder = InventoryItem.objects.create(
            name="Coffee grinder",
            category=equipment,
            quantity=Decimal("3.00"),
            unit="pcs",
            cost_per_unit=Decimal("180000.00"),
            is_active=True,
        )

        return {
            "coffee": coffee,
            "milk": milk,
            "cups": cups,
            "boxes": boxes,
            "grinder": grinder,
        }

    def create_purchases(self, inventory_data):
        supplier = Supplier.objects.create(
            name="Demo Coffee Supplier",
            contact="+7 777 000 00 00",
        )

        purchase = Purchase.objects.create(
            supplier=supplier,
            date=timezone.now().date() - timedelta(days=5),
            comment="Initial demo purchase",
        )

        PurchaseItem.objects.create(
            purchase=purchase,
            item=inventory_data["coffee"],
            quantity=Decimal("20.00"),
            price_per_unit=Decimal("4300.00"),
        )

        PurchaseItem.objects.create(
            purchase=purchase,
            item=inventory_data["cups"],
            quantity=Decimal("1000.00"),
            price_per_unit=Decimal("30.00"),
        )

        return {
            "supplier": supplier,
            "purchase": purchase,
        }

    def create_processes(self, org_data, employees):
        org = org_data["org"]

        procurement = Process.objects.create(
            organization=org,
            name="Procurement process",
            description="Monitoring of purchase requests, approval, payment and receiving.",
            is_active=True,
        )

        procurement_stages = [
            "Request created",
            "Manager approval",
            "Supplier invoice",
            "Payment",
            "Delivery",
            "Receiving and close",
        ]

        procurement_stage_objects = []
        for index, stage_name in enumerate(procurement_stages, start=1):
            procurement_stage_objects.append(
                Stage.objects.create(
                    process=procurement,
                    name=stage_name,
                    order=index,
                )
            )

        sales = Process.objects.create(
            organization=org,
            name="Sales order process",
            description="Monitoring of customer order, preparation, delivery and payment.",
            is_active=True,
        )

        sales_stages = [
            "Order received",
            "Preparation",
            "Quality check",
            "Delivery",
            "Customer payment",
            "Close order",
        ]

        sales_stage_objects = []
        for index, stage_name in enumerate(sales_stages, start=1):
            sales_stage_objects.append(
                Stage.objects.create(
                    process=sales,
                    name=stage_name,
                    order=index,
                )
            )

        service = Process.objects.create(
            organization=org,
            name="Service request process",
            description="Monitoring of internal service requests and execution time.",
            is_active=True,
        )

        service_stages = [
            "Request registered",
            "Assignment",
            "Execution",
            "Review",
            "Close request",
        ]

        service_stage_objects = []
        for index, stage_name in enumerate(service_stages, start=1):
            service_stage_objects.append(
                Stage.objects.create(
                    process=service,
                    name=stage_name,
                    order=index,
                )
            )

        return {
            "procurement": procurement,
            "procurement_stages": procurement_stage_objects,
            "sales": sales,
            "sales_stages": sales_stage_objects,
            "service": service,
            "service_stages": service_stage_objects,
        }

    def create_process_instances(self, processes_data, org_data, employees):
        today = timezone.now().date()

        instances = []

        instances.append(
            ProcessInstance.objects.create(
                process=processes_data["procurement"],
                name="Procurement #001 — coffee beans",
                manager=employees["manager"],
                planned_budget=Decimal("250000.00"),
                planned_end_date=today + timedelta(days=5),
                is_completed=False,
                current_stage=processes_data["procurement_stages"][2],
                branch=org_data["branch_main"],
                business_date=today,
            )
        )

        instances.append(
            ProcessInstance.objects.create(
                process=processes_data["procurement"],
                name="Procurement #002 — packaging",
                manager=employees["manager"],
                planned_budget=Decimal("120000.00"),
                planned_end_date=today - timedelta(days=2),
                is_completed=False,
                current_stage=processes_data["procurement_stages"][1],
                branch=org_data["branch_main"],
                business_date=today - timedelta(days=7),
            )
        )

        instances.append(
            ProcessInstance.objects.create(
                process=processes_data["procurement"],
                name="Procurement #003 — equipment",
                manager=employees["manager"],
                planned_budget=Decimal("600000.00"),
                planned_end_date=today - timedelta(days=1),
                is_completed=True,
                current_stage=processes_data["procurement_stages"][-1],
                branch=org_data["branch_second"],
                business_date=today - timedelta(days=12),
            )
        )

        instances.append(
            ProcessInstance.objects.create(
                process=processes_data["sales"],
                name="Sales order #001 — corporate client",
                manager=employees["manager"],
                planned_budget=Decimal("80000.00"),
                planned_end_date=today + timedelta(days=3),
                is_completed=False,
                current_stage=processes_data["sales_stages"][3],
                branch=org_data["branch_main"],
                business_date=today,
            )
        )

        instances.append(
            ProcessInstance.objects.create(
                process=processes_data["sales"],
                name="Sales order #002 — retail batch",
                manager=employees["manager"],
                planned_budget=Decimal("50000.00"),
                planned_end_date=today - timedelta(days=4),
                is_completed=True,
                current_stage=processes_data["sales_stages"][-1],
                branch=org_data["branch_main"],
                business_date=today - timedelta(days=10),
            )
        )

        instances.append(
            ProcessInstance.objects.create(
                process=processes_data["service"],
                name="Service request #001 — warehouse issue",
                manager=employees["manager"],
                planned_budget=Decimal("30000.00"),
                planned_end_date=today + timedelta(days=1),
                is_completed=False,
                current_stage=processes_data["service_stages"][2],
                branch=org_data["branch_second"],
                business_date=today,
            )
        )

        return instances

    def create_tasks(self, instances, employees):
        all_tasks = []

        for instance in instances:
            stages = list(instance.process.stages.all())

            for index, stage in enumerate(stages):
                if instance.is_completed:
                    status = "DONE"
                elif stage.order < instance.current_stage.order:
                    status = "DONE"
                elif stage.order == instance.current_stage.order:
                    status = "IN_PROGRESS"
                else:
                    status = "NEW"

                started_at = None
                completed_at = None

                if status in ["IN_PROGRESS", "DONE"]:
                    started_at = timezone.now() - timedelta(days=stage.order)

                if status == "DONE":
                    completed_at = timezone.now() - timedelta(days=max(1, 6 - stage.order))

                task = Task.objects.create(
                    process_instance=instance,
                    stage=stage,
                    title=f"{instance.name}: {stage.name}",
                    description="Demo task for business process monitoring.",
                    assignee=employees["employee"] if index % 2 == 0 else employees["employee2"],
                    status=status,
                    planned_hours=Decimal("4.00") + Decimal(index),
                    due_date=timezone.now().date() + timedelta(days=index - 2),
                    started_at=started_at,
                    completed_at=completed_at,
                )

                all_tasks.append(task)

        return all_tasks

    def create_transactions(self, finance_data, instances, tasks):
        today = timezone.now().date()

        for index, instance in enumerate(instances):
            if "Sales order" in instance.name:
                Transaction.objects.create(
                    account=finance_data["bank"],
                    category=finance_data["income_category"],
                    counterparty=finance_data["customer"],
                    process_instance=instance,
                    amount=Decimal("280000.00") + Decimal(index * 20000),
                    date=today - timedelta(days=index),
                    comment=f"Income for {instance.name}",
                )

                Transaction.objects.create(
                    account=finance_data["account"],
                    category=finance_data["logistics_expense"],
                    counterparty=finance_data["supplier"],
                    process_instance=instance,
                    amount=Decimal("-35000.00"),
                    date=today - timedelta(days=index),
                    comment=f"Delivery expense for {instance.name}",
                )

            elif "Service request" in instance.name:
                Transaction.objects.create(
                    account=finance_data["bank"],
                    category=finance_data["service_income"],
                    counterparty=finance_data["customer"],
                    process_instance=instance,
                    amount=Decimal("120000.00"),
                    date=today,
                    comment=f"Service income for {instance.name}",
                )

                Transaction.objects.create(
                    account=finance_data["account"],
                    category=finance_data["salary_expense"],
                    process_instance=instance,
                    amount=Decimal("-40000.00"),
                    date=today,
                    comment=f"Salary expense for {instance.name}",
                )

            else:
                Transaction.objects.create(
                    account=finance_data["account"],
                    category=finance_data["purchase_expense"],
                    counterparty=finance_data["supplier"],
                    process_instance=instance,
                    amount=Decimal("-90000.00") - Decimal(index * 15000),
                    date=today - timedelta(days=index),
                    comment=f"Procurement expense for {instance.name}",
                )

    def create_inventory_usages(self, inventory_data, tasks):
        if not tasks:
            return

        usable_tasks = tasks[:6]

        usage_plan = [
            (inventory_data["coffee"], Decimal("2.00")),
            (inventory_data["milk"], Decimal("10.00")),
            (inventory_data["cups"], Decimal("150.00")),
            (inventory_data["boxes"], Decimal("20.00")),
            (inventory_data["coffee"], Decimal("3.00")),
            (inventory_data["cups"], Decimal("200.00")),
        ]

        for task, usage_data in zip(usable_tasks, usage_plan):
            item, quantity = usage_data

            try:
                InventoryUsage.objects.create(
                    task=task,
                    item=item,
                    quantity=quantity,
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f"Inventory usage was not created: {exc}"
                    )
                )

    def create_stage_history(self, instances):
        now = timezone.now()

        for instance in instances:
            stages = list(instance.process.stages.all())

            start_time = now - timedelta(days=10)

            for index, stage in enumerate(stages):
                entered_at = start_time + timedelta(days=index * 2)

                if instance.is_completed:
                    left_at = entered_at + timedelta(hours=18 + index * 3)
                else:
                    if stage.order < instance.current_stage.order:
                        left_at = entered_at + timedelta(hours=20 + index * 4)
                    elif stage.order == instance.current_stage.order:
                        left_at = None
                    else:
                        continue

                StageHistory.objects.create(
                    process_instance=instance,
                    stage=stage,
                    entered_at=entered_at,
                    left_at=left_at,
                )