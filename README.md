"# Diploma_ERP_Monitoring"
"Python version: 3.11.7"
"Django==5.2.9 djangorestframework==3.16.1 python-dotenv==1.2.1"
"This project was created because of diploma work in university and has no connection with realm"
"Author: Miras Esimkhanov - mikodev667"

"About Project:"

1) Что это за система

У нас не “классический ERP в вакууме”, а web-платформа мониторинга эффективности бизнес-процессов.
Она объединяет операционные данные (процессы, задачи, склад, финансы) и на их основе строит мониторинг/KPI: сроки, bottlenecks, план-факт по бюджету, прибыльность инстансов.

2) Бизнес-слои
A) Operational layer (операционный контур)

Содержит первичные “факты бизнеса”:

Processes: Process, Stage, ProcessInstance — как устроен процесс и как он реально выполняется
Tasks: Task — что конкретно делают люди внутри процесса/этапа
Inventory: InventoryItem, InventoryUsage — остатки и списания под задачи
Finance: Transaction (+Account/Category/Counterparty) — деньги, привязанные к задачам и инстансам процессов
Orgs/People: Organization, Employee и роли пользователей

Это слой, где мы создаём/изменяем реальные сущности.

B) Monitoring & Analytics layer (контур мониторинга)

Это вычисления/агрегации:

Stage KPI: среднее время этапа, узкие места, зависшие инстансы на этапе
Instance KPI: duration, progress, overdue, plan-fact budget delta, profit/ cost / revenue
Dashboards/Reports: сводные показатели по периодам, менеджерские отчёты

Этот слой не “создаёт бизнес”, он читает операционные данные и считает метрики.

3) Доменная модель (как всё связано)
Process → Stage → ProcessInstance
Process — шаблон процесса (например “Inventory Replenishment”).
Stage — этапы внутри процесса, упорядочены order.
ProcessInstance — конкретный запуск процесса (“Restock — Dostyk — 2026-02-12”).
StageHistory = источник правды для времени этапов
При переходе инстанса на этап создаётся запись StageHistory(entered_at, left_at).
Это позволяет считать:
длительность каждого этапа
“сколько сейчас висим на этапе” (если left_at = NULL)
среднее время этапа по процессу и bottlenecks
Task = операционная работа внутри инстанса/этапа
Task привязан к process_instance и (обычно) к stage.
В идеале: этапы процесса отражаются набором задач, чтобы видеть “почему зависло”.
Finance.Transaction привязан к процессу и (опционально) к задаче
У Transaction есть process_instance (обязательно для аналитики прибыли/затрат).
task — позволяет детализировать, на каком шаге/этапе возник расход/доход.
InventoryUsage связывает склад и финансы через задачу
InventoryUsage(task, item, quantity) списывает остаток и при наличии cost_per_unit создаёт расходную транзакцию, привязанную к task и task.process_instance.
Так себестоимость материалов попадает в финансы автоматически.
4) Сервисный слой (services)
Зачем он нужен

Чтобы бизнес-логика была не в views и не размазана по моделям:

старт процесса
переход по этапам
корректное закрытие этапа и открытие нового
запись истории
Что делает start_process()
создаёт ProcessInstance
создаёт задачи по этапам (если у вас так принято)
ставит первый этап и пишет StageHistory
Что делает move_instance_to_stage()
закрывает текущий открытый этап (left_at = when)
создаёт новую запись StageHistory для нового этапа
обновляет instance.current_stage

Это фундамент для Stage KPI, потому что без истории этапов время не посчитать.

5) Views/Pages (представление)
Процессы
process_instance_list:
менеджер видит только свои инстансы (фильтр по manager)
админ/владелец видит все
process_instance_detail:
показывает карточки summary (deadline, current stage, profit, статус)
показывает stage timeline (из StageHistory)
показывает avg stage time (по процессу)
показывает задачи и транзакции

Важно: всё, что отображаем в UI по KPI — должно быть подготовлено в view (контекст), либо оформлено как property/метод модели, который корректно вызывается.

6) Где сейчас ключевые “точки эффективности”
StageHistory — главный источник для time-KPI по этапам.
Transaction.process_instance — основа для profit/cost/revenue по процессу.
planned_budget / planned_end_date — план-факт и просрочка.
InventoryUsage — автоматизация себестоимости и привязка расхода к работе.
7) Роли и доступы (логика отображения)

У вас уже заложена идея:

EMPLOYEE — видит свои задачи/работу
MANAGER — видит процессы, где он менеджер, и аналитику по ним
OWNER/ADMIN — видит общий мониторинг и отчётность

Это отражается в фильтрации списков и в содержимом dashboard.

8) Как это “в итоге работает” как платформа мониторинга
Создаём Process и Stage (шаблон процесса)
Запускаем ProcessInstance (кейс/заказ/инцидент)
Двигаем его по этапам → пишется StageHistory
В процессе создаются задачи, исполняются людьми
По задачам и инстансу создаются Transaction (доходы/расходы)
InventoryUsage списывает склад и создаёт транзакции себестоимости
Monitoring слой строит KPI:
где узкие места (по среднему времени этапов)
где “зависло сейчас” (по открытому этапу и времени на нём)
просрочено ли (planned_end_date vs today)
перерасход ли (cost vs planned_budget)
прибыльность (sum transactions)
