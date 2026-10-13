.DEFAULT_GOAL := help

.PHONY: $(shell sed -nE 's/^([a-z-]+):.*/\1/p' $(firstword $(MAKEFILE_LIST)))

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(firstword $(MAKEFILE_LIST)) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

dev: ## Install dependencies and pre-commit hooks, migrate, run the API with reload on :8000
	@uv sync
	@uv run pre-commit install
	@$(MAKE) --no-print-directory migrate
	@uv run granian --interface asgi --reload --reload-paths src kommunalka.presentation.app:app

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

migrate: ## Apply migrations to the local database
	@uv run alembic upgrade head

migration: ## Create a migration from model changes: make migration name=add_notes
	@test -n "$(name)" || (echo "usage: make migration name=<name>" && exit 1)
	@uv run alembic revision --autogenerate -m "$(name)"

COMPOSE := docker compose -f docker/compose.yaml -f docker/compose.build.yaml $(if $(wildcard .env),--env-file .env)
UP := $(COMPOSE) up -d --wait

up: ## Build and start the stack in Docker
	@$(UP)

down: ## Stop the stack (the database volume is kept)
	@$(COMPOSE) down

logs: ## Follow logs: make logs [service=backup]
	@$(COMPOSE) logs -f

# Backups are made by the external service sqlite-repo-backuper (see docker/compose.yaml);
# one-off commands run in a container of it, next to the database volume.
BACKUP := $(COMPOSE) run --rm --no-deps backup

backup: ## Back up the database to GitHub now
	@$(BACKUP) backup

backups: ## List backups in GitHub
	@$(BACKUP) list

restore: ## Restore the database from GitHub and start the stack: make restore [tag=<tag>]
	@$(COMPOSE) down
	@$(BACKUP) restore $(or $(tag),latest) -o /data/kommunalka.db --force \
		|| { echo "restore failed, starting the stack with the database as it was"; $(UP); exit 1; }
	@$(UP)
