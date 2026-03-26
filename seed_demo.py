# seed_demo.py
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from orgs.models import Organization
from processes.models import Process, Stage, ProcessInstance, StageHistory
from finance.models import Account, Category, Counterparty, Transaction

# Inventory is optional
try:
    from inventory.models import InventoryCategory, InventoryItem
    HAS_INVENTORY = True
except Exception:
    HAS_INVENTORY = False


# ---------------- helpers ----------------
def field_names(model):
    return {f.name for f in model._meta.fields}


def safe_create(model, **kwargs):
    fn = field_names(model)
    clean = {k: v for k, v in kwargs.items() if k in fn}
    return model.objects.create(**clean)


def safe_update_qs(model, pk, **kwargs):
    fn = field_names(model)
    clean = {k: v for k, v in kwargs.items() if k in fn}
    if clean:
        model.objects.filter(pk=pk).update(**clean)


def aware_dt(y, m, d, hh=12, mm=0):
    return timezone.make_aware(datetime(y, m, d, hh, mm, 0))


def get_or_create_simple(model, defaults=None, **lookup):
    defaults = defaults or {}
    obj, _ = model.objects.get_or_create(defaults=defaults, **lookup)
    return obj


def ensure_account(name, currency="KZT"):
    return get_or_create_simple(Account, name=name, currency=currency)


def ensure_category(name, type_):
    return get_or_create_simple(Category, name=name, type=type_)


def ensure_cp(name):
    return get_or_create_simple(Counterparty, name=name)


def ensure_process(org, name, stage_names, description=None):
    lookup = {"organization": org, "name": name}
    proc = Process.objects.filter(**lookup).first()
    if not proc:
        proc = safe_create(Process, **lookup, description=description)

    # Deterministic stages for demo
    Stage.objects.filter(process=proc).delete()
    stages = []
    for i, nm in enumerate(stage_names, start=1):
        stages.append(safe_create(Stage, process=proc, name=nm, order=i))
    return proc, stages


def add_hist(pi, stage, entered, left=None):
    return safe_create(
        StageHistory,
        process_instance=pi,
        stage=stage,
        entered_at=entered,
        left_at=left,
    )


def add_tx(pi, account, category, amount, d, comment, counterparty=None):
    return safe_create(
        Transaction,
        account=account,
        category=category,
        counterparty=counterparty,
        process_instance=pi,
        amount=Decimal(str(amount)),
        date=d,  # DateField in your project
        comment=comment,
    )


def reset_demo(prefix="DEMO/"):
    demo_qs = ProcessInstance.objects.filter(name__startswith=prefix)
    Transaction.objects.filter(process_instance__in=demo_qs).delete()
    StageHistory.objects.filter(process_instance__in=demo_qs).delete()
    demo_qs.delete()


def seed_inventory():
    if not HAS_INVENTORY:
        return

    item_fn = field_names(InventoryItem)

    cat_beans = get_or_create_simple(InventoryCategory, name="Coffee beans")
    cat_dairy = get_or_create_simple(InventoryCategory, name="Dairy")
    cat_pack = get_or_create_simple(InventoryCategory, name="Packaging")

    def ensure_item(name, category, quantity, unit, cpu):
        obj = InventoryItem.objects.filter(name=name).first()
        if not obj:
            obj = safe_create(
                InventoryItem,
                name=name,
                category=category,
                quantity=Decimal(str(quantity)),
                unit=unit,
                cost_per_unit=Decimal(str(cpu)),
                is_active=True,
            )
        else:
            upd = {}
            if "category" in item_fn:
                upd["category"] = category
            if "quantity" in item_fn:
                upd["quantity"] = Decimal(str(quantity))
            if "unit" in item_fn:
                upd["unit"] = unit
            if "cost_per_unit" in item_fn:
                upd["cost_per_unit"] = Decimal(str(cpu))
            if "is_active" in item_fn:
                upd["is_active"] = True
            if upd:
                InventoryItem.objects.filter(pk=obj.pk).update(**upd)
        return obj

    ensure_item("Arabica blend (espresso) 1 kg", cat_beans, 48, "kg", "6150")
    ensure_item("Milk 2.5% (1L)", cat_dairy, 220, "l", "640")
    ensure_item("Paper cups 250ml", cat_pack, 3000, "pcs", "42")
    ensure_item("Plastic lids 250ml", cat_pack, 3000, "pcs", "18")
    ensure_item("Sugar sticks", cat_pack, 4000, "pcs", "6")


# ---------------- main seed ----------------
@db_transaction.atomic
def run():
    reset_demo("DEMO/")

    # Organization
    org = Organization.objects.first()
    if org is None:
        org = safe_create(Organization, name="QahwaLab KZ")

    # Accounts
    acc_kaspi = ensure_account("Kaspi Business KZT", "KZT")
    acc_cash = ensure_account("Cash Desk KZT", "KZT")
    acc_bank = ensure_account("Halyk Business KZT", "KZT")

    # Categories (Income)
    cat_sales_drinks = ensure_category("Sales - coffee & drinks", "INCOME")
    cat_sales_food = ensure_category("Sales - desserts", "INCOME")
    cat_b2b = ensure_category("Sales - B2B / catering", "INCOME")

    # Categories (Expense)
    cat_beans = ensure_category("COGS - coffee beans", "EXPENSE")
    cat_milk = ensure_category("COGS - milk", "EXPENSE")
    cat_pack = ensure_category("COGS - packaging", "EXPENSE")
    cat_log = ensure_category("Logistics - delivery", "EXPENSE")
    cat_urg = ensure_category("Extra costs - urgent delivery", "EXPENSE")
    cat_maint = ensure_category("Maintenance - equipment repair", "EXPENSE")
    cat_util = ensure_category("OPEX - rent & utilities", "EXPENSE")
    cat_mkt = ensure_category("OPEX - marketing / ads", "EXPENSE")
    cat_hr = ensure_category("OPEX - HR / training", "EXPENSE")

    # Counterparties
    cp_beans = ensure_cp("TOO BeanCraft Roasters")
    cp_milk = ensure_cp("TOO MilkWay Dairy")
    cp_pack = ensure_cp("TOO PackPro KZ")
    cp_serv = ensure_cp("TOO ServiceTech KZ")
    cp_ads = ensure_cp("Meta Ads / Google Ads")
    cp_util = ensure_cp("Landlord & Utilities (aggregate)")
    cp_cust = ensure_cp("Customers (aggregate)")
    cp_b2b = ensure_cp("B2B Client: Business Center Dostyk")

    # Processes
    proc_supply, st_supply = ensure_process(
        org,
        "Inventory Replenishment",
        ["Request Submission", "Approval", "Invoice Receipt", "Payment", "Delivery", "Receiving and Closure"],
        description="Replenishment of branch inventory and supplies",
    )
    s_req, s_app, s_inv, s_pay, s_del, s_cls = st_supply

    proc_maint, st_maint = ensure_process(
        org,
        "Equipment Repair",
        ["Issue Registration", "Diagnosis", "Quotation Approval", "Repair", "Verification and Closure"],
        description="Repair and restoration of coffee equipment",
    )
    m_rep, m_diag, m_quote, m_fix, m_close = st_maint

    proc_mkt, st_mkt = ensure_process(
        org,
        "Marketing Campaign Execution",
        ["Brief Preparation", "Approval", "Launch", "Monitoring and Optimization", "Reporting and Closure"],
        description="Execution and performance tracking of marketing campaigns",
    )
    k_brief, k_appr, k_launch, k_run, k_report = st_mkt

    proc_hr, st_hr = ensure_process(
        org,
        "Barista Onboarding",
        ["Candidate Selection", "Document Processing", "Training", "First Shift", "Onboarding Closure"],
        description="Hiring and onboarding of new baristas",
    )
    h_sel, h_docs, h_train, h_shift, h_prob = st_hr

    proc_opex, st_opex = ensure_process(
        org,
        "Operating Expense Payment",
        ["Expense Registration", "Approval", "Invoice Receipt", "Payment", "Closure"],
        description="Payment of rent and utility expenses",
    )
    o_req, o_app, o_inv, o_pay, o_cls = st_opex

    proc_b2b, st_b2b = ensure_process(
        org,
        "B2B Order Fulfillment",
        ["Order Registration", "Approval", "Preparation", "Delivery", "Closure"],
        description="Fulfillment of corporate catering orders",
    )
    b_req, b_app, b_prep, b_del, b_cls = st_b2b

    # -----------------------
    # DATA: PREVIOUS MONTH (Feb 2026) + CURRENT (Mar 2026)
    # -----------------------

    # ===== Inventory Replenishment (Feb, completed) =====
    pi_f1 = safe_create(
        ProcessInstance,
        process=proc_supply,
        name="DEMO/ Inventory Replenishment - Dostyk - 2026-02-12 (completed)",
        planned_budget=Decimal("275000.00"),
        planned_end_date=date(2026, 2, 14),
        is_completed=True,
        current_stage=s_cls,
    )
    safe_update_qs(ProcessInstance, pi_f1.pk, started_at=aware_dt(2026, 2, 12, 9, 20))
    add_hist(pi_f1, s_req, aware_dt(2026, 2, 12, 9, 20), aware_dt(2026, 2, 12, 10, 10))
    add_hist(pi_f1, s_app, aware_dt(2026, 2, 12, 10, 10), aware_dt(2026, 2, 12, 16, 0))
    add_hist(pi_f1, s_inv, aware_dt(2026, 2, 12, 16, 0), aware_dt(2026, 2, 13, 10, 30))
    add_hist(pi_f1, s_pay, aware_dt(2026, 2, 13, 10, 30), aware_dt(2026, 2, 13, 11, 0))
    add_hist(pi_f1, s_del, aware_dt(2026, 2, 13, 14, 0), aware_dt(2026, 2, 14, 10, 30))
    add_hist(pi_f1, s_cls, aware_dt(2026, 2, 14, 10, 30), aware_dt(2026, 2, 14, 11, 0))

    add_tx(pi_f1, acc_kaspi, cat_beans, -118800, date(2026, 2, 12), "Coffee beans 19 kg @ 6,252", cp_beans)
    add_tx(pi_f1, acc_kaspi, cat_milk, -67600, date(2026, 2, 12), "Milk 104 L @ 650", cp_milk)
    add_tx(pi_f1, acc_kaspi, cat_pack, -46200, date(2026, 2, 12), "Cups and lids 1,100 pcs", cp_pack)
    add_tx(pi_f1, acc_cash, cat_log, -32000, date(2026, 2, 13), "Delivery service (Almaty)", cp_pack)
    add_tx(pi_f1, acc_kaspi, cat_sales_drinks, 352900, date(2026, 2, 14), "POS sales (drinks) - Dostyk", cp_cust)
    add_tx(pi_f1, acc_kaspi, cat_sales_food, 64500, date(2026, 2, 14), "POS sales (desserts) - Dostyk", cp_cust)

    # ===== Inventory Replenishment (Feb, stuck on payment) =====
    pi_f2 = safe_create(
        ProcessInstance,
        process=proc_supply,
        name="DEMO/ Inventory Replenishment - Mega - 2026-02-20 (stuck on payment)",
        planned_budget=Decimal("310000.00"),
        planned_end_date=date(2026, 2, 22),
        is_completed=False,
        current_stage=s_pay,
    )
    safe_update_qs(ProcessInstance, pi_f2.pk, started_at=aware_dt(2026, 2, 20, 11, 15))
    add_hist(pi_f2, s_req, aware_dt(2026, 2, 20, 11, 15), aware_dt(2026, 2, 20, 12, 0))
    add_hist(pi_f2, s_app, aware_dt(2026, 2, 20, 12, 0), aware_dt(2026, 2, 20, 17, 10))
    add_hist(pi_f2, s_inv, aware_dt(2026, 2, 20, 17, 10), aware_dt(2026, 2, 21, 10, 30))
    add_hist(pi_f2, s_pay, aware_dt(2026, 2, 21, 10, 30), None)

    add_tx(pi_f2, acc_bank, cat_beans, -145600, date(2026, 2, 20), "Coffee beans 23 kg @ 6,330", cp_beans)
    add_tx(pi_f2, acc_bank, cat_milk, -72800, date(2026, 2, 20), "Milk 112 L @ 650", cp_milk)
    add_tx(pi_f2, acc_bank, cat_pack, -52400, date(2026, 2, 20), "Cups and lids 1,250 pcs", cp_pack)
    add_tx(pi_f2, acc_bank, cat_sales_drinks, 301400, date(2026, 2, 22), "POS sales (drinks) - Mega", cp_cust)

    # ===== Equipment Repair (Feb, bottleneck at quote) =====
    pi_f3 = safe_create(
        ProcessInstance,
        process=proc_maint,
        name="DEMO/ Espresso Machine Repair - Mega - 2026-02-08 (waiting quote)",
        planned_budget=Decimal("210000.00"),
        planned_end_date=date(2026, 2, 10),
        is_completed=False,
        current_stage=m_quote,
    )
    safe_update_qs(ProcessInstance, pi_f3.pk, started_at=aware_dt(2026, 2, 8, 9, 0))
    add_hist(pi_f3, m_rep, aware_dt(2026, 2, 8, 9, 0), aware_dt(2026, 2, 8, 9, 35))
    add_hist(pi_f3, m_diag, aware_dt(2026, 2, 8, 9, 35), aware_dt(2026, 2, 8, 13, 10))
    add_hist(pi_f3, m_quote, aware_dt(2026, 2, 8, 13, 10), None)
    add_tx(pi_f3, acc_bank, cat_maint, -26000, date(2026, 2, 8), "Diagnostics service call", cp_serv)

    # ===== Marketing Campaign (Feb, closed) =====
    pi_f4 = safe_create(
        ProcessInstance,
        process=proc_mkt,
        name="DEMO/ February New Menu Campaign - 2026-02-05 (closed)",
        planned_budget=Decimal("220000.00"),
        planned_end_date=date(2026, 2, 16),
        is_completed=True,
        current_stage=k_report,
    )
    safe_update_qs(ProcessInstance, pi_f4.pk, started_at=aware_dt(2026, 2, 5, 10, 0))
    add_hist(pi_f4, k_brief, aware_dt(2026, 2, 5, 10, 0), aware_dt(2026, 2, 5, 14, 0))
    add_hist(pi_f4, k_appr, aware_dt(2026, 2, 5, 14, 0), aware_dt(2026, 2, 6, 12, 0))
    add_hist(pi_f4, k_launch, aware_dt(2026, 2, 6, 12, 0), aware_dt(2026, 2, 6, 12, 20))
    add_hist(pi_f4, k_run, aware_dt(2026, 2, 6, 12, 20), aware_dt(2026, 2, 15, 18, 0))
    add_hist(pi_f4, k_report, aware_dt(2026, 2, 15, 18, 0), aware_dt(2026, 2, 16, 12, 0))

    add_tx(pi_f4, acc_kaspi, cat_mkt, -98000, date(2026, 2, 6), "Ads spend - launch week", cp_ads)
    add_tx(pi_f4, acc_kaspi, cat_mkt, -62000, date(2026, 2, 10), "Ads spend - optimization", cp_ads)
    add_tx(pi_f4, acc_kaspi, cat_sales_drinks, 205500, date(2026, 2, 14), "Campaign uplift (drinks) - aggregate", cp_cust)
    add_tx(pi_f4, acc_kaspi, cat_sales_food, 38200, date(2026, 2, 14), "Campaign uplift (desserts) - aggregate", cp_cust)

    # ===== OPEX Payment (Feb, closed) =====
    pi_f5 = safe_create(
        ProcessInstance,
        process=proc_opex,
        name="DEMO/ Operating Expense Payment for February 2026 (closed)",
        planned_budget=Decimal("505000.00"),
        planned_end_date=date(2026, 2, 28),
        is_completed=True,
        current_stage=o_cls,
    )
    safe_update_qs(ProcessInstance, pi_f5.pk, started_at=aware_dt(2026, 2, 26, 18, 0))
    add_hist(pi_f5, o_req, aware_dt(2026, 2, 26, 18, 0), aware_dt(2026, 2, 26, 18, 20))
    add_hist(pi_f5, o_app, aware_dt(2026, 2, 26, 18, 20), aware_dt(2026, 2, 26, 19, 10))
    add_hist(pi_f5, o_inv, aware_dt(2026, 2, 26, 19, 10), aware_dt(2026, 2, 27, 10, 0))
    add_hist(pi_f5, o_pay, aware_dt(2026, 2, 27, 10, 0), aware_dt(2026, 2, 27, 10, 15))
    add_hist(pi_f5, o_cls, aware_dt(2026, 2, 27, 10, 15), aware_dt(2026, 2, 27, 10, 40))

    add_tx(pi_f5, acc_bank, cat_util, -252000, date(2026, 2, 27), "Rent - Dostyk branch (Feb)", cp_util)
    add_tx(pi_f5, acc_bank, cat_util, -230000, date(2026, 2, 27), "Rent - Mega branch (Feb)", cp_util)
    add_tx(pi_f5, acc_bank, cat_util, -47000, date(2026, 2, 27), "Utilities (electricity/water) - Feb", cp_util)

    # ===== Current month (Mar 2026) examples =====

    # Inventory Replenishment (Mar, completed)
    pi_m1 = safe_create(
        ProcessInstance,
        process=proc_supply,
        name="DEMO/ Inventory Replenishment - Dostyk - 2026-03-04 (completed)",
        planned_budget=Decimal("285000.00"),
        planned_end_date=date(2026, 3, 6),
        is_completed=True,
        current_stage=s_cls,
    )
    safe_update_qs(ProcessInstance, pi_m1.pk, started_at=aware_dt(2026, 3, 4, 9, 35))
    add_hist(pi_m1, s_req, aware_dt(2026, 3, 4, 9, 35), aware_dt(2026, 3, 4, 10, 20))
    add_hist(pi_m1, s_app, aware_dt(2026, 3, 4, 10, 20), aware_dt(2026, 3, 4, 16, 10))
    add_hist(pi_m1, s_inv, aware_dt(2026, 3, 4, 16, 10), aware_dt(2026, 3, 5, 10, 40))
    add_hist(pi_m1, s_pay, aware_dt(2026, 3, 5, 10, 40), aware_dt(2026, 3, 5, 11, 15))
    add_hist(pi_m1, s_del, aware_dt(2026, 3, 6, 9, 10), aware_dt(2026, 3, 6, 12, 20))
    add_hist(pi_m1, s_cls, aware_dt(2026, 3, 6, 12, 20), aware_dt(2026, 3, 6, 12, 45))

    add_tx(pi_m1, acc_kaspi, cat_beans, -124800, date(2026, 3, 4), "Coffee beans 20 kg @ 6,240", cp_beans)
    add_tx(pi_m1, acc_kaspi, cat_milk, -70200, date(2026, 3, 4), "Milk 108 L @ 650", cp_milk)
    add_tx(pi_m1, acc_kaspi, cat_pack, -49800, date(2026, 3, 4), "Cups and lids 1,200 pcs", cp_pack)
    add_tx(pi_m1, acc_kaspi, cat_sales_drinks, 356400, date(2026, 3, 6), "POS sales (drinks) - Dostyk", cp_cust)
    add_tx(pi_m1, acc_kaspi, cat_sales_food, 68900, date(2026, 3, 6), "POS sales (desserts) - Dostyk", cp_cust)

    # Marketing Campaign (Mar, closed) -- FIX: cat_mkt (not cat_ads)
    pi_m2 = safe_create(
        ProcessInstance,
        process=proc_mkt,
        name="DEMO/ Spring Weekend Promotion Campaign - 2026-03-03 (closed)",
        planned_budget=Decimal("180000.00"),
        planned_end_date=date(2026, 3, 10),
        is_completed=True,
        current_stage=k_report,
    )
    safe_update_qs(ProcessInstance, pi_m2.pk, started_at=aware_dt(2026, 3, 3, 10, 0))
    add_hist(pi_m2, k_brief, aware_dt(2026, 3, 3, 10, 0), aware_dt(2026, 3, 3, 15, 30))
    add_hist(pi_m2, k_appr, aware_dt(2026, 3, 3, 15, 30), aware_dt(2026, 3, 4, 12, 0))
    add_hist(pi_m2, k_launch, aware_dt(2026, 3, 4, 12, 0), aware_dt(2026, 3, 4, 12, 20))
    add_hist(pi_m2, k_run, aware_dt(2026, 3, 4, 12, 20), aware_dt(2026, 3, 10, 18, 0))
    add_hist(pi_m2, k_report, aware_dt(2026, 3, 10, 18, 0), aware_dt(2026, 3, 10, 19, 0))

    add_tx(pi_m2, acc_bank, cat_mkt, -172000, date(2026, 3, 4), "Paid social and search ads for spring promotion", cp_ads)
    add_tx(pi_m2, acc_kaspi, cat_sales_drinks, 143200, date(2026, 3, 9), "Campaign uplift (drinks) - aggregate", cp_cust)
    add_tx(pi_m2, acc_kaspi, cat_sales_food, 25400, date(2026, 3, 9), "Campaign uplift (desserts) - aggregate", cp_cust)

    # B2B Order (Mar, closed)
    pi_m3 = safe_create(
        ProcessInstance,
        process=proc_b2b,
        name="DEMO/ B2B Catering Order - Business Center Dostyk - 2026-03-20 (closed)",
        planned_budget=Decimal("160000.00"),
        planned_end_date=date(2026, 3, 20),
        is_completed=True,
        current_stage=b_cls,
    )
    safe_update_qs(ProcessInstance, pi_m3.pk, started_at=aware_dt(2026, 3, 19, 9, 0))
    add_hist(pi_m3, b_req, aware_dt(2026, 3, 19, 9, 0), aware_dt(2026, 3, 19, 9, 40))
    add_hist(pi_m3, b_app, aware_dt(2026, 3, 19, 9, 40), aware_dt(2026, 3, 19, 11, 0))
    add_hist(pi_m3, b_prep, aware_dt(2026, 3, 19, 11, 0), aware_dt(2026, 3, 19, 14, 10))
    add_hist(pi_m3, b_del, aware_dt(2026, 3, 20, 8, 0), aware_dt(2026, 3, 20, 9, 15))
    add_hist(pi_m3, b_cls, aware_dt(2026, 3, 20, 9, 15), aware_dt(2026, 3, 20, 9, 30))

    add_tx(pi_m3, acc_kaspi, cat_beans, -38400, date(2026, 3, 19), "Coffee beans 6 kg @ 6,400 (catering batch)", cp_beans)
    add_tx(pi_m3, acc_kaspi, cat_milk, -18200, date(2026, 3, 19), "Milk 28 L @ 650 (catering)", cp_milk)
    add_tx(pi_m3, acc_kaspi, cat_pack, -12600, date(2026, 3, 19), "Cups and lids 300 pcs (catering)", cp_pack)
    add_tx(pi_m3, acc_bank, cat_b2b, 229000, date(2026, 3, 20), "Invoice paid: B2B catering for Business Center Dostyk", cp_b2b)

    # Inventory seed
    seed_inventory()

    demo_pi_count = ProcessInstance.objects.filter(name__startswith="DEMO/").count()
    demo_tx_count = Transaction.objects.filter(process_instance__name__startswith="DEMO/").count()

    print(f"DONE: demo instances={demo_pi_count}, demo transactions={demo_tx_count}, inventory={HAS_INVENTORY}")


run()