.PHONY: up up-back up-front down down-clean reup reup-back reup-front test test-back test-front lint lint-back lint-front test-local test-back-local test-front-local precommit install-hooks logs logs-back shell

up:
	docker compose up --build -d

up-back:
	docker compose up --build -d db rabbitmq backend worker payment-operator

up-front:
	docker compose up --build -d frontend

down:
	docker compose down

down-clean:
	docker compose down -v

reup:
	docker compose down
	docker compose up --build -d

reup-back:
	docker compose down backend worker payment-operator
	docker compose up --build -d db rabbitmq backend worker payment-operator

reup-front:
	docker compose down frontend
	docker compose up --build -d frontend

test:
	docker compose exec backend python manage.py test
	docker compose exec frontend npm test

test-back:
	docker compose exec backend python manage.py test

test-front:
	docker compose exec frontend npm test

lint:
	$(MAKE) lint-back
	$(MAKE) lint-front

lint-back:
	.venv/bin/ruff check backend payment_operator

lint-front:
	cd frontend && npm run lint

test-local:
	$(MAKE) test-back-local
	$(MAKE) test-front-local

test-back-local:
	cd backend && CELERY_TASK_ALWAYS_EAGER=1 ../.venv/bin/python manage.py test

test-front-local:
	cd frontend && npm test

precommit:
	$(MAKE) lint
	$(MAKE) test-local

test-docker:
	docker compose build --quiet
	docker compose run --rm backend python manage.py test
	docker compose down --timeout 5

install-hooks:
	.venv/bin/pre-commit install
	.venv/bin/pre-commit install --hook-type pre-push

logs:
	docker compose logs -f

logs-back:
	docker compose logs -f backend worker

shell:
	docker compose exec backend python manage.py shell
