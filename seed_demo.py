from datetime import date, datetime
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from django.conf import settings

from orgs.models import Organization
from processes.models import Process, Stage, ProcessInstance, StageHistory
from finance.models import Account, Category, Counterparty, Transaction

# inventory app might be optional
try:
    from inventory.models import InventoryCategory, InventoryItem
    HAS_INVENTORY = True
except Exception:
    HAS_INVENTORY = False


# ---------------- helpers (safe: only existing fields) ----------------
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
    # Process might have description, might not.
    lookup = {"organization": org, "name": name}
    proc = Process.objects.filter(**lookup).first()
    if not proc:
        proc = safe_create(Process, **lookup, description=description)

    # reset stages deterministically for demo
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
    # Transaction.date in your project is DateField (you used timezone.now().date())
    return safe_create(
        Transaction,
        account=account,
        category=category,
        counterparty=counterparty,
        process_instance=pi,
        amount=Decimal(str(amount)),
        date=d,
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

    cat_fn = field_names(InventoryCategory)
    item_fn = field_names(InventoryItem)

    # categories
    cat_beans = get_or_create_simple(InventoryCategory, name="Coffee beans")
    cat_dairy = get_or_create_simple(InventoryCategory, name="Dairy")
    cat_pack  = get_or_create_simple(InventoryCategory, name="Packaging")

    # items (quantities realistic for 2 branches)
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
            # just refresh demo values
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

    ensure_item("Arabica blend (espresso) 1 kg", cat_beans, 42, "kg", "6150")
    ensure_item("Milk 2.5% (1L)", cat_dairy, 180, "l", "640")
    ensure_item("Paper cups 250ml", cat_pack, 2400, "pcs", "42")
    ensure_item("Plastic lids 250ml", cat_pack, 2400, "pcs", "18")
    ensure_item("Sugar sticks", cat_pack, 3000, "pcs", "6")


@db_transaction.atomic
def run():
    # 0) clean previous demo
    reset_demo("DEMO/")

    # 1) base entities
    org = Organization.objects.first()
    if org is None:
        org = safe_create(Organization, name="QahwaLab KZ")

    # accounts
    acc_kaspi = ensure_account("Kaspi Business KZT", "KZT")
    acc_cash  = ensure_account("Cash Desk KZT", "KZT")
    acc_bank  = ensure_account("Halyk Business KZT", "KZT")

    # categories (income)
    cat_sales_drinks = ensure_category("Sales - coffee & drinks", "INCOME")
    cat_sales_food   = ensure_category("Sales - desserts", "INCOME")
    cat_b2b          = ensure_category("Sales - B2B / catering", "INCOME")

    # categories (expense)
    cat_beans = ensure_category("COGS - coffee beans", "EXPENSE")
    cat_milk  = ensure_category("COGS - milk", "EXPENSE")
    cat_pack  = ensure_category("COGS - packaging", "EXPENSE")
    cat_log   = ensure_category("Logistics - delivery", "EXPENSE")
    cat_urg   = ensure_category("Extra costs - urgent delivery", "EXPENSE")
    cat_maint = ensure_category("Maintenance - equipment repair", "EXPENSE")
    cat_util  = ensure_category("OPEX - rent & utilities", "EXPENSE")
    cat_mkt   = ensure_category("OPEX - marketing / ads", "EXPENSE")
    cat_hr    = ensure_category("OPEX - HR / training", "EXPENSE")

    # counterparties
    cp_beans = ensure_cp("TOO BeanCraft Roasters")
    cp_milk  = ensure_cp("TOO MilkWay Dairy")
    cp_pack  = ensure_cp("TOO PackPro KZ")
    cp_serv  = ensure_cp("TOO ServiceTech KZ")
    cp_ads   = ensure_cp("Meta Ads / Google Ads")
    cp_util  = ensure_cp("Landlord & Utilities (aggregate)")
    cp_cust  = ensure_cp("Customers (aggregate)")
    cp_b2b   = ensure_cp("B2B Client: Business Center Dostyk")

    # 2) processes & stages
    proc_supply, st_supply = ensure_process(
        org,
        "Supply Chain - weekly restock",
        ["Request created", "Manager approval", "Vendor invoice", "Payment", "Delivery", "Receiving & close"],
        description="Weekly procurement & restock for branches",
    )
    s_req, s_app, s_inv, s_pay, s_del, s_cls = st_supply

    proc_maint, st_maint = ensure_process(
        org,
        "Maintenance - equipment incident",
        ["Incident reported", "Diagnose", "Parts / Quote", "Repair", "QA & close"],
        description="Fix coffee equipment incidents",
    )
    m_rep, m_diag, m_quote, m_fix, m_close = st_maint

    proc_mkt, st_mkt = ensure_process(
        org,
        "Marketing - campaign execution",
        ["Brief created", "Creative approval", "Launch", "Run & optimize", "Close & report"],
        description="Launch & track marketing campaigns",
    )
    k_brief, k_appr, k_launch, k_run, k_report = st_mkt

    proc_hr, st_hr = ensure_process(
        org,
        "HR - onboarding barista",
        ["Candidate selected", "Documents", "Training", "First shift", "Probation close"],
        description="Hire & onboard baristas",
    )
    h_sel, h_docs, h_train, h_shift, h_prob = st_hr

    # 3) instances + histories + transactions (Jan + Feb 2026)

    # --- SUPPLY (Jan completed)
    pi_p1 = safe_create(
        ProcessInstance,
        process=proc_supply,
        name="DEMO/ Restock - Dostyk branch - 2026-01-10 (completed)",
        planned_budget=Decimal("285000.00"),
        planned_end_date=date(2026, 1, 13),
        is_completed=True,
        current_stage=s_cls,
    )
    safe_update_qs(ProcessInstance, pi_p1.pk, started_at=aware_dt(2026, 1, 10, 9, 35))
    add_hist(pi_p1, s_req, aware_dt(2026, 1, 10, 9, 35), aware_dt(2026, 1, 10, 10, 20))
    add_hist(pi_p1, s_app, aware_dt(2026, 1, 10, 10, 20), aware_dt(2026, 1, 10, 16, 10))
    add_hist(pi_p1, s_inv, aware_dt(2026, 1, 10, 16, 10), aware_dt(2026, 1, 11, 10, 40))
    add_hist(pi_p1, s_pay, aware_dt(2026, 1, 11, 10, 40), aware_dt(2026, 1, 11, 11, 15))
    add_hist(pi_p1, s_del, aware_dt(2026, 1, 11, 11, 15), aware_dt(2026, 1, 12, 10, 10))
    add_hist(pi_p1, s_cls, aware_dt(2026, 1, 12, 10, 10), aware_dt(2026, 1, 12, 10, 55))

    add_tx(pi_p1, acc_kaspi, cat_beans, -121680, date(2026, 1, 10), "Beans 19.5 kg @ 6,240", cp_beans)
    add_tx(pi_p1, acc_kaspi, cat_milk,  -69450,  date(2026, 1, 10), "Milk 2.5% 105 L @ 661", cp_milk)
    add_tx(pi_p1, acc_kaspi, cat_pack,  -28800,  date(2026, 1, 10), "Cups+Lids set 680 pcs", cp_pack)
    add_tx(pi_p1, acc_cash,  cat_log,   -39500,  date(2026, 1, 11), "Delivery within Almaty", cp_pack)
    add_tx(pi_p1, acc_kaspi, cat_sales_drinks, 342900, date(2026, 1, 12), "POS sales (drinks) - Dostyk", cp_cust)
    add_tx(pi_p1, acc_kaspi, cat_sales_food,    60800, date(2026, 1, 12), "POS sales (desserts) - Dostyk", cp_cust)

    # --- SUPPLY (Jan overdue, stuck approval)
    pi_p2 = safe_create(
        ProcessInstance,
        process=proc_supply,
        name="DEMO/ Restock - Mega branch - 2026-01-22 (overdue + overrun)",
        planned_budget=Decimal("410000.00"),
        planned_end_date=date(2026, 1, 24),
        is_completed=False,
        current_stage=s_app,
    )
    safe_update_qs(ProcessInstance, pi_p2.pk, started_at=aware_dt(2026, 1, 22, 11, 5))
    add_hist(pi_p2, s_req, aware_dt(2026, 1, 22, 11, 5),  aware_dt(2026, 1, 22, 11, 50))
    add_hist(pi_p2, s_app, aware_dt(2026, 1, 22, 11, 50), None)

    add_tx(pi_p2, acc_kaspi, cat_beans, -236250, date(2026, 1, 22), "Beans 38.5 kg @ 6,136", cp_beans)
    add_tx(pi_p2, acc_kaspi, cat_milk,  -96640,  date(2026, 1, 22), "Milk 2.5% 145 L @ 666", cp_milk)
    add_tx(pi_p2, acc_cash,  cat_urg,   -98500,  date(2026, 1, 23), "Urgent delivery + surcharge", cp_pack)
    add_tx(pi_p2, acc_kaspi, cat_sales_drinks, 318400, date(2026, 1, 24), "POS sales (drinks) - Mega", cp_cust)
    add_tx(pi_p2, acc_kaspi, cat_sales_food,    57400, date(2026, 1, 24), "POS sales (desserts) - Mega", cp_cust)

    # --- SUPPLY (Feb stuck payment)
    pi_p3 = safe_create(
        ProcessInstance,
        process=proc_supply,
        name="DEMO/ Restock - Dostyk branch - 2026-02-07 (stuck on payment)",
        planned_budget=Decimal("330000.00"),
        planned_end_date=date(2026, 2, 9),
        is_completed=False,
        current_stage=s_pay,
    )
    safe_update_qs(ProcessInstance, pi_p3.pk, started_at=aware_dt(2026, 2, 7, 14, 5))
    add_hist(pi_p3, s_req, aware_dt(2026, 2, 7, 14, 5),  aware_dt(2026, 2, 7, 14, 55))
    add_hist(pi_p3, s_app, aware_dt(2026, 2, 7, 14, 55), aware_dt(2026, 2, 7, 18, 20))
    add_hist(pi_p3, s_inv, aware_dt(2026, 2, 7, 18, 20), aware_dt(2026, 2, 8, 10, 10))
    add_hist(pi_p3, s_pay, aware_dt(2026, 2, 8, 10, 10), None)

    add_tx(pi_p3, acc_kaspi, cat_pack,  -51200, date(2026, 2, 7), "Cups+Lids set 1,200 pcs", cp_pack)
    add_tx(pi_p3, acc_kaspi, cat_beans, -168588, date(2026, 2, 7), "Beans 27 kg @ 6,244", cp_beans)
    add_tx(pi_p3, acc_kaspi, cat_milk,   -79920, date(2026, 2, 7), "Milk 2.5% 120 L @ 666", cp_milk)
    add_tx(pi_p3, acc_kaspi, cat_sales_drinks, 402300, date(2026, 2, 8), "POS sales (drinks) - Dostyk", cp_cust)
    add_tx(pi_p3, acc_kaspi, cat_sales_food,    74100, date(2026, 2, 8), "POS sales (desserts) - Dostyk", cp_cust)

    # --- MAINTENANCE (Jan closed)
    pi_m1 = safe_create(
        ProcessInstance,
        process=proc_maint,
        name="DEMO/ Grinder #2 - Dostyk - 2026-01-15 (repair closed)",
        planned_budget=Decimal("95000.00"),
        planned_end_date=date(2026, 1, 16),
        is_completed=True,
        current_stage=m_close,
    )
    safe_update_qs(ProcessInstance, pi_m1.pk, started_at=aware_dt(2026, 1, 15, 8, 20))
    add_hist(pi_m1, m_rep,   aware_dt(2026, 1, 15, 8, 20), aware_dt(2026, 1, 15, 9, 5))
    add_hist(pi_m1, m_diag,  aware_dt(2026, 1, 15, 9, 5),  aware_dt(2026, 1, 15, 12, 10))
    add_hist(pi_m1, m_quote, aware_dt(2026, 1, 15, 12, 10), aware_dt(2026, 1, 15, 16, 40))
    add_hist(pi_m1, m_fix,   aware_dt(2026, 1, 15, 16, 40), aware_dt(2026, 1, 16, 10, 25))
    add_hist(pi_m1, m_close, aware_dt(2026, 1, 16, 10, 25), aware_dt(2026, 1, 16, 11, 0))
    add_tx(pi_m1, acc_bank, cat_maint, -84500, date(2026, 1, 16), "Grinder repair + calibration", cp_serv)

    # --- MARKETING (Jan closed)
    pi_k1 = safe_create(
        ProcessInstance,
        process=proc_mkt,
        name="DEMO/ Campaign - January weekend promo - 2026-01-05 (closed)",
        planned_budget=Decimal("180000.00"),
        planned_end_date=date(2026, 1, 12),
        is_completed=True,
        current_stage=k_report,
    )
    safe_update_qs(ProcessInstance, pi_k1.pk, started_at=aware_dt(2026, 1, 5, 10, 0))
    add_hist(pi_k1, k_brief,  aware_dt(2026, 1, 5, 10, 0),  aware_dt(2026, 1, 5, 15, 30))
    add_hist(pi_k1, k_appr,   aware_dt(2026, 1, 5, 15, 30), aware_dt(2026, 1, 6, 12, 0))
    add_hist(pi_k1, k_launch, aware_dt(2026, 1, 6, 12, 0),  aware_dt(2026, 1, 6, 12, 20))
    add_hist(pi_k1, k_run,    aware_dt(2026, 1, 6, 12, 20), aware_dt(2026, 1, 11, 23, 0))
    add_hist(pi_k1, k_report, aware_dt(2026, 1, 11, 23, 0), aware_dt(2026, 1, 12, 11, 10))

    add_tx(pi_k1, acc_kaspi, cat_mkt, -62400, date(2026, 1, 6), "Ads spend - first week", cp_ads)
    add_tx(pi_k1, acc_kaspi, cat_mkt, -51750, date(2026, 1, 9), "Ads spend - optimization", cp_ads)
    add_tx(pi_k1, acc_kaspi, cat_sales_drinks, 198900, date(2026, 1, 11), "Campaign uplift (drinks) - aggregate", cp_cust)
    add_tx(pi_k1, acc_kaspi, cat_sales_food,    36400, date(2026, 1, 11), "Campaign uplift (desserts) - aggregate", cp_cust)

    # --- HR (Jan closed)
    pi_h1 = safe_create(
        ProcessInstance,
        process=proc_hr,
        name="DEMO/ Onboarding - Barista (Dostyk) - 2026-01-18 (closed)",
        planned_budget=Decimal("65000.00"),
        planned_end_date=date(2026, 1, 25),
        is_completed=True,
        current_stage=h_prob,
    )
    safe_update_qs(ProcessInstance, pi_h1.pk, started_at=aware_dt(2026, 1, 18, 10, 15))
    add_hist(pi_h1, h_sel,   aware_dt(2026, 1, 18, 10, 15), aware_dt(2026, 1, 18, 14, 10))
    add_hist(pi_h1, h_docs,  aware_dt(2026, 1, 18, 14, 10), aware_dt(2026, 1, 19, 12, 0))
    add_hist(pi_h1, h_train, aware_dt(2026, 1, 19, 12, 0),  aware_dt(2026, 1, 23, 18, 30))
    add_hist(pi_h1, h_shift, aware_dt(2026, 1, 23, 18, 30), aware_dt(2026, 1, 24, 22, 0))
    add_hist(pi_h1, h_prob,  aware_dt(2026, 1, 24, 22, 0),  aware_dt(2026, 1, 25, 12, 0))

    add_tx(pi_h1, acc_bank, cat_hr, -18500, date(2026, 1, 19), "Training materials + uniforms", cp_util)
    add_tx(pi_h1, acc_bank, cat_hr, -32000, date(2026, 1, 24), "Mentor hours (internal cost)", cp_util)

    # --- OPEX utilities entry (Jan month-end)
    pi_u1 = safe_create(
        ProcessInstance,
        process=proc_supply,
        name="DEMO/ Monthly close - Rent & Utilities - 2026-01-31 (posted)",
        planned_budget=Decimal("520000.00"),
        planned_end_date=date(2026, 2, 2),
        is_completed=True,
        current_stage=s_cls,
    )
    safe_update_qs(ProcessInstance, pi_u1.pk, started_at=aware_dt(2026, 1, 31, 18, 0))
    add_hist(pi_u1, s_req, aware_dt(2026, 1, 31, 18, 0), aware_dt(2026, 1, 31, 18, 15))
    add_hist(pi_u1, s_app, aware_dt(2026, 1, 31, 18, 15), aware_dt(2026, 1, 31, 19, 0))
    add_hist(pi_u1, s_inv, aware_dt(2026, 1, 31, 19, 0), aware_dt(2026, 2, 1, 10, 0))
    add_hist(pi_u1, s_pay, aware_dt(2026, 2, 1, 10, 0), aware_dt(2026, 2, 1, 10, 20))
    add_hist(pi_u1, s_cls, aware_dt(2026, 2, 1, 10, 20), aware_dt(2026, 2, 1, 10, 40))

    add_tx(pi_u1, acc_bank, cat_util, -268450, date(2026, 1, 31), "Rent - Dostyk branch (Jan)", cp_util)
    add_tx(pi_u1, acc_bank, cat_util, -241900, date(2026, 1, 31), "Rent - Mega branch (Jan)", cp_util)
    add_tx(pi_u1, acc_bank, cat_util,  -48750, date(2026, 1, 31), "Utilities (electricity/water) - Jan", cp_util)

    # --- B2B catering income (Jan)
    pi_b2b = safe_create(
        ProcessInstance,
        process=proc_supply,
        name="DEMO/ B2B Catering - Business Center Dostyk - 2026-01-27 (delivered)",
        planned_budget=Decimal("160000.00"),
        planned_end_date=date(2026, 1, 27),
        is_completed=True,
        current_stage=s_cls,
    )
    safe_update_qs(ProcessInstance, pi_b2b.pk, started_at=aware_dt(2026, 1, 26, 9, 0))
    add_hist(pi_b2b, s_req, aware_dt(2026, 1, 26, 9, 0),  aware_dt(2026, 1, 26, 9, 40))
    add_hist(pi_b2b, s_app, aware_dt(2026, 1, 26, 9, 40), aware_dt(2026, 1, 26, 11, 0))
    add_hist(pi_b2b, s_inv, aware_dt(2026, 1, 26, 11, 0), aware_dt(2026, 1, 26, 13, 30))
    add_hist(pi_b2b, s_pay, aware_dt(2026, 1, 26, 13, 30), aware_dt(2026, 1, 26, 14, 10))
    add_hist(pi_b2b, s_del, aware_dt(2026, 1, 27, 8, 0),  aware_dt(2026, 1, 27, 9, 15))
    add_hist(pi_b2b, s_cls, aware_dt(2026, 1, 27, 9, 15), aware_dt(2026, 1, 27, 9, 30))

    add_tx(pi_b2b, acc_kaspi, cat_beans, -38400, date(2026, 1, 26), "Beans 6 kg @ 6,400 (catering batch)", cp_beans)
    add_tx(pi_b2b, acc_kaspi, cat_milk,  -18200, date(2026, 1, 26), "Milk 28 L @ 650 (catering)", cp_milk)
    add_tx(pi_b2b, acc_kaspi, cat_pack,  -12600, date(2026, 1, 26), "Cups+Lids 300 pcs (catering)", cp_pack)
    add_tx(pi_b2b, acc_bank,  cat_b2b,  229000, date(2026, 1, 27), "Invoice paid: B2B catering (Dostyk BC)", cp_b2b)

    # 4) inventory
    seed_inventory()

    demo_pi_count = ProcessInstance.objects.filter(name__startswith="DEMO/").count()
    demo_tx_count = Transaction.objects.filter(process_instance__name__startswith="DEMO/").count()
    print(f"DONE: demo instances={demo_pi_count}, demo transactions={demo_tx_count}, inventory={HAS_INVENTORY}")


run()
