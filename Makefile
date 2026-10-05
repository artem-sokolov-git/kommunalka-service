.DEFAULT_GOAL := help
.PHONY: help install dev test lint fmt check migrate migration up down logs backup

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## Install dependencies and pre-commit hooks
	uv sync
	uv run pre-commit install

dev: migrate ## Run the API with reload on http://localhost:8000
	uv run granian --interface asgi --reload --reload-paths src kommunalka.presentation.app:app

test: ## Run tests
	uv run pytest

lint: ## Check lint, formatting and types
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check

fmt: ## Format and autofix
	uv run ruff format .
	uv run ruff check --fix .

check: lint test ## Lint and test

migrate: ## Apply migrations to the local database
	uv run alembic upgrade head

migration: ## Create a migration from model changes: make migration name=add_notes
	@test -n "$(name)" || (echo "usage: make migration name=<name>" && exit 1)
	uv run alembic revision --autogenerate -m "$(name)"

up: ## Build and start the stack in Docker
	docker compose up -d --build --wait

down: ## Stop the stack (the database in ./data is kept)
	docker compose down

logs: ## Follow API logs
	docker compose logs -f api

backup: ## Back up data/kommunalka.db into data/backups/ (safe while running)
	uv run python -m kommunalka.infrastructure.db.backup data/kommunalka.db data/backups
