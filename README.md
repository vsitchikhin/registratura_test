# Registratura

Сервис пополнения кошелька через платёжного оператора.

## Быстрый старт

```bash
make up
```

Откройте [http://localhost:3000](http://localhost:3000) — введите сумму, нажмите "Пополнить", через 1-3 секунды платёж будет обработан.

Для полного сброса (удаление БД):

```bash
make down-clean && make up
```

## Архитектура

6 Docker-контейнеров, один порт наружу (`3000`):

```
Frontend (nginx :80)
  ├── static files (React build)
  └── /api/* → proxy → Backend (Django :8000)
                          ├── POST /api/payments/  → Celery task → RabbitMQ
                          │                                          ↓
                          │                                       Worker
                          │                                          ↓
                          │                              Payment Operator (FastAPI :8080)
                          │                                          ↓
                          └── POST /api/webhooks/payment/  ← webhook callback
                                    ↓
                              Wallet.balance += amount
                              (atomic, idempotent)

PostgreSQL ← все данные
```

| Контейнер | Технология | Роль |
|-----------|-----------|------|
| `db` | PostgreSQL 16 | Хранение данных |
| `rabbitmq` | RabbitMQ 3 | Брокер очередей |
| `backend` | Django 5 + DRF | REST API, webhook endpoint |
| `worker` | Celery (тот же образ) | Отправка платежей оператору |
| `payment-operator` | FastAPI | Mock внешнего платёжного сервиса |
| `frontend` | React + Vite + nginx | UI + reverse proxy |

## Денежная модель

- Все суммы хранятся в **копейках** через `DecimalField` — точная арифметика без потерь на промежуточных вычислениях.
- **Ledger** (`LedgerEntry`) — журнал всех переходов статуса платежа. Каждая смена статуса (`NEW → PROCESSING → SUCCEEDED/FAILED`) фиксируется отдельной записью.
- `Wallet.balance_minor` — денормализованный кэш, обновляется только при `SUCCEEDED`.
- Баланс верифицируем: `SUM(LedgerEntry.amount_minor) WHERE status=SUCCEEDED == Wallet.balance_minor`.

## Гарантии целостности

| Угроза | Защита |
|--------|--------|
| Двойной webhook | Unique `event_id` + `get_or_create` в `PaymentWebhookLog` |
| Race condition на платеже | `select_for_update()` на `Payment` |
| Двойное зачисление | `UniqueConstraint(payment, status)` на `LedgerEntry` (DB constraint) |
| Race condition на балансе | `F('balance_minor') + amount` (атомарный SQL increment) |
| Неконсистентность данных | `transaction.atomic()` — всё или ничего |
| Дубль Celery task | Проверка `status != NEW` перед переводом в `PROCESSING` |

## FSM статусов платежа

```
NEW → PROCESSING → SUCCEEDED
                 → FAILED
```

Терминальные статусы (`SUCCEEDED`, `FAILED`) — необратимы.

## Валидация суммы

- Принимается как строка (`"100.50"`)
- Конвертация через `Decimal` (не float)
- Минимум: `0.01` RUB
- Максимум: `10 000 000.00` RUB
- Максимум 2 знака после запятой
- Ноль и отрицательные — отклоняются

## Команды

```bash
# Запуск
make build           # Собрать образы
make up              # Поднять всё
make up-back         # Только backend-стек (db, rabbitmq, backend, worker, operator)
make up-front        # Только frontend
make down            # Остановить
make down-clean      # Остановить + удалить volumes

# Пересборка
make reup            # Пересобрать и перезапустить всё
make reup-back       # Пересобрать backend-стек
make reup-front      # Пересобрать frontend

# Тесты
make test            # Все тесты в Docker
make test-back       # Backend тесты (Postgres)
make test-back-local # Backend тесты локально (SQLite)
make test-front      # Frontend тесты

# Качество кода
make lint            # Все линтеры
make lint-back       # Ruff (Python)
make lint-front      # ESLint (JS)

# Утилиты
make logs            # Логи всех сервисов
make logs-back       # Логи backend + worker
make shell           # Django shell
```

## Тесты (26 штук)

| Группа | Что проверяем |
|--------|--------------|
| FSM (7) | Допустимые и запрещённые переходы статусов |
| Валидация суммы (9) | Корректные суммы, ноль, отрицательные, 3+ знака, превышение лимита |
| API (3) | Создание платежа, список, баланс |
| Webhook success/fail (2) | Зачисление при `succeeded`, запись в ledger при `failed` без изменения баланса |
| Идемпотентность (3) | Дубль webhook, конфликт статусов, несуществующий платёж |
| Накопление баланса (1) | Баланс корректно суммируется после нескольких платежей |
| Worker (1) | Повторный вызов для уже обработанного платежа — no-op |

## Тестовые данные

При первом запуске миграция создаёт 5 платежей в разных статусах:

| Сумма | Статус | Баланс |
|-------|--------|--------|
| 100.50 ₽ | `succeeded` | +100.50 |
| 500.00 ₽ | `succeeded` | +500.00 |
| 2 500.00 ₽ | `succeeded` | +2 500.00 |
| 750.00 ₽ | `failed` | — |
| 300.00 ₽ | `processing` | — |

Начальный баланс: **3 100.50 ₽**. Для каждого платежа создан полный набор записей в ledger.

## Payment Operator (mock)

- Принимает платёж, случайно определяет результат: ~80% `succeeded`, ~20% `failed`
- Задержка 1-3 секунды (имитация обработки)
- С вероятностью ~20% отправляет webhook дважды (демонстрация защиты от дублей)

## Осознанные упрощения

- Один пользователь, один кошелёк, без авторизации
- Одна валюта (RUB)
- `SECRET_KEY` захардкожен (dev-only)
- Нет HTTPS, rate limiting, HMAC-подписи webhook
- Нет reconciliation для "зависших" платежей (`PROCESSING` без ответа)
- Payment operator не хранит состояние (stateless mock)
