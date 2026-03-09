from django.db import transaction
from django.utils import timezone
from tasks.models import Task
from .models import ProcessInstance, Stage
from datetime import timedelta
from django.db.models import Avg, F, ExpressionWrapper, DurationField, Count
from .models import StageHistory


@transaction.atomic
def start_process(process, name):
    """
    Создаёт запуск процесса и автоматически генерирует задачи по этапам.
    Инициализирует первый этап и журнал этапов.
    """
    instance = ProcessInstance.objects.create(
        process=process,
        name=name,
    )

    # 1) Создаём задачи по этапам
    stages = process.stages.order_by("order")
    for stage in stages:
        Task.objects.create(
            process_instance=instance,
            stage=stage,
            title=stage.name,
        )

    # 2) Ставим первый этап как текущий и пишем StageHistory
    first_stage = stages.first()
    if first_stage:
        move_instance_to_stage(instance, first_stage)

    return instance


@transaction.atomic
def move_instance_to_stage(instance: ProcessInstance, new_stage: Stage, when=None) -> StageHistory:
    when = when or timezone.now()

    # защита от этапа другого процесса
    if new_stage.process_id != instance.process_id:
        raise ValueError("new_stage does not belong to instance.process")

    # 1) закрыть текущий этап, если он открыт
    StageHistory.objects.filter(
        process_instance=instance,
        left_at__isnull=True,
    ).update(left_at=when)

    # 2) создать запись нового этапа
    row = StageHistory.objects.create(
        process_instance=instance,
        stage=new_stage,
        entered_at=when,
        left_at=None,
    )

    # 3) обновить instance
    instance.current_stage = new_stage
    instance.save(update_fields=["current_stage"])

    return row


def avg_stage_time_by_process(process_id: int):
    """
    Среднее время этапов для конкретного процесса.
    """
    duration_expr = ExpressionWrapper(
        F("left_at") - F("entered_at"),
        output_field=DurationField()
    )

    return (
        StageHistory.objects
        .filter(
            process_instance__process_id=process_id,
            left_at__isnull=False,
        )
        .values("stage_id", "stage__name", "stage__order")
        .annotate(
            avg_time=Avg(duration_expr),
            passes=Count("id"),
        )
        .order_by("-avg_time")
    )


def bottlenecks(process_id: int, top_n: int = 3):
    """
    Узкие места = этапы с самым большим средним временем.
    """
    return list(avg_stage_time_by_process(process_id)[:top_n])


def stuck_instances(process_id: int, hours: int = 24):
    """
    Текущие зависшие на этапах.
    """
    threshold = timezone.now() - timedelta(hours=hours)

    return (
        StageHistory.objects
        .filter(
            process_instance__process_id=process_id,
            left_at__isnull=True,
            entered_at__lt=threshold,
        )
        .select_related("process_instance", "stage", "process_instance__manager")
        .order_by("entered_at")
    )


def stuck_by_stage(process_id: int, hours: int = 24):
    """
    Где чаще всего 'застревают' (агрегация по этапам).
    """
    threshold = timezone.now() - timedelta(hours=hours)

    return (
        StageHistory.objects
        .filter(
            process_instance__process_id=process_id,
            left_at__isnull=True,
            entered_at__lt=threshold,
        )
        .values("stage_id", "stage__name", "stage__order")
        .annotate(stuck_count=Count("id"))
        .order_by("-stuck_count")
    )


def instance_stage_timeline(instance_id: int):
    """
    История этапов конкретного instance + длительность каждого этапа.
    """
    return (
        StageHistory.objects
        .filter(process_instance_id=instance_id)
        .select_related("stage")
        .order_by("entered_at")
    )


def current_stage_age(instance_id: int):
    """
    Сколько instance находится на текущем этапе (timedelta) или None.
    """
    row = (
        StageHistory.objects
        .filter(process_instance_id=instance_id, left_at__isnull=True)
        .only("entered_at")
        .first()
    )
    if not row:
        return None
    return timezone.now() - row.entered_at


def avg_stage_time_for_process(process_id: int):
    """
    Среднее время этапов по процессу (агрегат по всем instances процесса).
    """
    duration_expr = ExpressionWrapper(
        F("left_at") - F("entered_at"),
        output_field=DurationField()
    )

    return (
        StageHistory.objects
        .filter(
            process_instance__process_id=process_id,
            left_at__isnull=False,
        )
        .values("stage_id", "stage__name", "stage__order")
        .annotate(
            avg_time=Avg(duration_expr),
            passes=Count("id"),
        )
        .order_by("-avg_time")
    )