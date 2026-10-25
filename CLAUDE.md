# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Service for tracking utility bills of a household: meters, monthly readings, tariffs, bills.
Python 3.13, FastAPI on Granian, PostgreSQL via SQLAlchemy Core (no ORM session), Alembic, Jinja2.

## Commands

```sh
make check                            # ruff check, ruff format --check, ty check, pytest
make fmt                              # ruff format + ruff check --fix
make setup                            # uv sync + pre-commit hooks; the app itself runs only in Docker
make migration name=<slug>            # alembic revision --autogenerate against a throwaway PostgreSQL container
make up / make down / make logs       # Docker stack; needs KS_PG_PASS (letters and digits) from the environment or .env
make backup                           # one-off dump now (postgres-backup-local service, into ./backups)
make backups / make restore            # list dumps; restore the latest or file=daily/<file>
uv run pytest tests/domain/entities/test_reading.py::test_next_reading_follows_last
```

Run `alembic` from the repo root: its config is `[tool.alembic]` in `pyproject.toml`
(`alembic.ini` only configures logging). Settings live in `infrastructure/config/`
(`Settings`, pydantic-settings), read through `get_settings()` only at the edges (app
factory, migrations `env.py`): `KS_`-prefixed environment variables or
`.env`. All settings have defaults. `alembic` needs a database (`KS_DATABASE_URL`): use
`make migration` instead of calling it by hand.

## Architecture

Clean layers under `src/kommunalka/`, dependencies point inward only. Each layer has its own
`CLAUDE.md` with its rules; read it before changing the layer:

- `domain/` — entities, value objects, billing rules and bill calculation; no framework imports.
- `application/` — `UnitOfWork` and repository ports, use cases (write) and queries (read).
- `infrastructure/db/` — table models, SQL repositories, `SqlUnitOfWork`, migrations.
  `infrastructure/config/` — `Settings` and `get_settings`.
- `presentation/` — JSON API (`api/`) and Jinja2 pages (`web/`), assembled in `app.py`.

`tests/` mirrors `src/` (see `tests/CLAUDE.md`); `docker/` holds the Docker stack
(see `docker/CLAUDE.md`).

## Conventions

- Commits: one-line Conventional Commits (`feat: ...`, `fix(api): ...`), no body, no trailer.
- Ruff line length 100; `allowed-confusables` covers Cyrillic, since UI texts and data are
  Russian. Write a non-breaking space as `" "`, never as a literal character (RUF001).
- Code, identifiers and docs are in English; UI texts are Russian (see
  `src/kommunalka/presentation/CLAUDE.md` for where they go).
- `legacy/` (`sqlite_import.py`, the one-off import of the old SQLite database), `data/` and
  `backups/` are local only: ignored by git, excluded from ty and the Docker build. The
  volume `kommunalka-pg` holds real data: never `docker compose down -v`; check pages on a
  copy (restore a dump from `backups/` into a throwaway PostgreSQL container and point
  `KS_DATABASE_URL` at it), never change it in place. The volume `kommunalka-data` is the old
  SQLite database, kept as a fallback.
