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

up: bws-check ## Build and start the stack in Docker, secrets from the Bitwarden project $BWS_PROJECT_ID
	@bws run --project-id $(BWS_PROJECT_ID) -- docker compose up -d --build --wait

down: ## Stop the stack (the database in ./data is kept)
	@docker compose down

logs: ## Follow API logs
	@docker compose logs -f api

backup: bws-check ## Back up the database into data/backups/ and push a dump to GitHub now
	@KOMMUNALKA_DATABASE_URL=sqlite:///data/kommunalka.db \
		bws run --project-id $(BWS_PROJECT_ID) -- uv run python -m kommunalka.infrastructure.db.backup
