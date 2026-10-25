.DEFAULT_GOAL := help

.PHONY: $(shell sed -nE 's/^([a-z-]+):.*/\1/p' $(firstword $(MAKEFILE_LIST)))

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(firstword $(MAKEFILE_LIST)) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install dependencies and pre-commit hooks (the app itself runs only in Docker: make up)
	@uv sync
	@uv run pre-commit install

test: ## Run tests
	@uv run pytest

lint: ## Check lint, formatting and types
	@uv run ruff check .
	@uv run ruff format --check .
	@uv run ty check

fmt: ## Format and autofix
	@uv run ruff format .
	@uv run ruff check --fix .

check: lint test ## Lint and test

# Autogenerate compares the models with a database at head: a throwaway PostgreSQL does.
MIGRATION_DB := ks-migration-db
MIGRATION_URL := postgresql+psycopg://kommunalka:kommunalka@127.0.0.1:55432/kommunalka

migration: ## Create a migration from model changes: make migration name=add_notes
	@test -n "$(name)" || (echo "usage: make migration name=<name>" && exit 1)
	@docker run -d --rm --name $(MIGRATION_DB) -p 127.0.0.1:55432:5432 \
		-e POSTGRES_USER=kommunalka -e POSTGRES_PASSWORD=kommunalka postgres:18.6 >/dev/null
	@trap 'docker stop $(MIGRATION_DB) >/dev/null' EXIT; \
		until docker exec $(MIGRATION_DB) pg_isready -h 127.0.0.1 -U kommunalka >/dev/null 2>&1; do sleep 1; done; \
		export KS_DATABASE_URL=$(MIGRATION_URL); \
		uv run alembic upgrade head && uv run alembic revision --autogenerate -m "$(name)"

COMPOSE := docker compose -f docker/compose.yaml -f docker/compose.build.yaml $(if $(wildcard .env),--env-file .env)
UP := $(COMPOSE) up -d --wait

up: ## Build and start the stack in Docker
	@$(UP)

down: ## Stop the stack (the database volume is kept)
	@$(COMPOSE) down

logs: ## Follow logs: make logs [service=backup]
	@$(COMPOSE) logs -f

# Backups are made by the image postgres-backup-local (see docker/compose.yaml) into the
# ./backups; one-off commands run in a container of it, next to the database.
BACKUP := $(COMPOSE) run --rm --no-deps backup

backup: ## Back up the database now
	@$(BACKUP) /backup.sh

backups: ## List backups
	@$(BACKUP) sh -c 'ls -lh /backups/daily /backups/weekly /backups/monthly'

restore: ## Restore the database from a backup and start the stack: make restore [file=daily/<file>]
	@$(COMPOSE) stop app
	@$(BACKUP) sh -c 'zcat /backups/$(or $(file),last/kommunalka-latest.sql.gz) \
		| PGPASSWORD=$$POSTGRES_PASSWORD psql -h db -U $$POSTGRES_USER -d $$POSTGRES_DB \
			-v ON_ERROR_STOP=1 --single-transaction -q' \
		|| { echo "restore failed, starting the stack with the database as it was"; $(UP); exit 1; }
	@$(UP)
