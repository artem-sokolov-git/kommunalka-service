.DEFAULT_GOAL := help

# BWS_PROJECT_ID for up and backup can live in .env.
-include .env

.PHONY: $(shell sed -nE 's/^([a-z-]+):.*/\1/p' $(firstword $(MAKEFILE_LIST)))

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(firstword $(MAKEFILE_LIST)) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## Install dependencies and pre-commit hooks
	@uv sync
	@uv run pre-commit install

dev: migrate ## Run the API with reload on http://localhost:8000
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

bws-check:
	@command -v bws >/dev/null || { echo "bws not found: https://bitwarden.com/help/secrets-manager-cli/"; exit 1; }
	@test -n "$(BWS_PROJECT_ID)" || { echo "BWS_PROJECT_ID is not set: put the project id into .env"; exit 1; }

COMPOSE := docker compose -f docker/compose.yaml $(if $(wildcard .env),--env-file .env)
UP := bws run --project-id $(BWS_PROJECT_ID) -- $(COMPOSE) up -d --build --wait

up: bws-check ## Build and start the stack in Docker, secrets from the Bitwarden project $BWS_PROJECT_ID
	@$(UP)

down: ## Stop the stack (the database volume is kept)
	@$(COMPOSE) down

logs: ## Follow logs: make logs [service=backup]
	@$(COMPOSE) logs -f $(or $(service),api)

# Backup scripts run once in a container of the backup service, next to the database volume.
DB_TOOL := bws run --project-id $(BWS_PROJECT_ID) -- $(COMPOSE) run --rm --no-deps --build backup

backup: bws-check ## Back up the database in the volume and push a dump to GitHub now
	@$(DB_TOOL) backup

backups: bws-check ## List backups in GitHub
	@$(DB_TOOL) backups

restore: bws-check ## Restore the database from GitHub and start the stack: make restore [args="--revision <commit>"]
	@$(COMPOSE) down
	@$(DB_TOOL) restore $(args) \
		|| { echo "restore failed, starting the stack with the database as it was"; $(UP); exit 1; }
	@$(UP)
