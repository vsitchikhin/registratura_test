# Registratura

Тестовое задание: сервис пополнения кошелька. Сейчас настроен каркас проекта и инфраструктура без бизнес-логики.

## Стек

- Backend: Django + DRF + Celery
- Queue: RabbitMQ
- DB: PostgreSQL
- Payment operator mock: FastAPI
- Frontend: React + Vite + nginx

## Запуск

```bash
make up
```

Фронтенд будет доступен на `http://localhost:3000`.

## Команды

```bash
make up
make up-back
make up-front
make down
make down-clean
make reup
make test-back
make test-front
make logs
```

## Текущий этап

Настроены конфигурации сервисов, Dockerfile, `docker-compose.yml`, nginx reverse proxy, Makefile и базовые health endpoints. Бизнес-модели, API платежей, ledger, webhook handler и frontend-функциональность будут добавляться следующими шагами.
