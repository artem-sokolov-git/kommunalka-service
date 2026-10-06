# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Service for tracking utility bills of a household: meters, monthly readings, tariffs, bills.
Python 3.13, FastAPI on Granian, SQLite via SQLAlchemy Core (no ORM session), Alembic, Jinja2.

## Commands

```sh
make install                          # uv sync + pre-commit hooks
make check                            # ruff check, ruff format --check, ty check, pytest
make fmt                              # ruff format + ruff check --fix
make dev                              # migrate ./kommunalka.db, run Granian with reload on :8000
make migration name=<slug>            # alembic revision --autogenerate
make up / make down / make logs       # Docker stack (migrate service, then api)
make backup                           # online copy of data/kommunalka.db into data/backups/
uv run pytest tests/domain/entities/test_reading.py::test_next_reading_follows_last
```

Run `alembic` from the repo root: its config is `[tool.alembic]` in `pyproject.toml`
(`alembic.ini` only configures logging). The database URL comes from `KOMMUNALKA_DATABASE_URL`
(default `sqlite:///kommunalka.db`); in Docker it is `data/kommunalka.db` on the host via a
bind mount.

## Architecture

Clean layers under `src/kommunalka/`, dependencies point inward only:

- `domain/` — frozen `slots` dataclasses, no framework imports. Entities reference each other
  by UUID. Value objects (`DateRange`, `Unit`, `MeteredBillLine`/`FixedBillLine`) live in
  `value_objects.py`, errors (all subclass `DomainError`) in `exceptions.py`. Rules that need
  several entities are plain functions next to the entity: `ensure_unique_*`,
  `ensure_no_overlap`, `ensure_not_billed`, `next_reading`, `readings_for_month`.
  `services/billing.py::calculate_bill` builds a `Bill` from meters, readings and tariffs.
- `application/` — `UnitOfWork` and repository `Protocol`s (ports), use cases in
  `use_cases/` (write) and `queries.py` (read, including read models for pages). Use cases
  only load data, call the domain and save; business rules belong in `domain/`.
- `infrastructure/db/` — table models are `DeclarativeBase` classes used **only** as schema
  and query targets through `Connection`; repositories map rows to domain objects by hand.
  `SqlUnitOfWork` translates `IntegrityError` into `application.exceptions.ConflictError`.
- `presentation/` — `api/` (JSON, Pydantic schemas) and `web/` (Jinja2 pages, static CSS),
  assembled in `presentation/app.py` (entrypoint `kommunalka.presentation.app:app`).
  `presentation/errors.py::describe_error` maps errors to HTTP codes for both; `app.py`
  renders HTML errors for `/` and `/view/...`, JSON elsewhere.

Things that span several files:

- **Unit of work**: every use case/query is one `with uow:` block = one connection and
  transaction; leaving it without `commit()` rolls back. Don't call another query/use case
  inside a `with uow:` block — re-entering opens a new connection; use repositories directly.
- **Uniqueness** is checked twice: by `ensure_*` functions in use cases (readable errors) and
  by DB unique constraints (races). Tariff overlap has no DB constraint.
- **Billing rules**: a reading taken in month M closes month M−1 (`Reading.billing_period`);
  one reading per meter and month (`readings.billing_month` column enforces it); the first
  reading is a baseline. Tariffs are `TariffPeriod`s with optional `valid_to` (open-ended);
  for unmetered services the price is a monthly amount added to bills automatically unless
  `fixed_amounts` overrides it. A price change (`change_price` → `next_tariff_period`)
  starts on the 1st of a month after the latest price, closes the open period the day
  before and can't touch billed months; `undo_price_change` removes the latest price
  and reopens the previous one unless a bill uses it. A bill is a whole calendar month; once issued,
  readings of that month can't change.
- **Money and readings** are `Decimal`: stored as text (`DecimalString`), sent as JSON
  strings, rounded to kopecks with `ROUND_HALF_UP`. Bill line order is kept in
  `bill_lines.position`.
- **Migrations** live in `infrastructure/db/migrations/` (`script_location` is a package
  path). `env.py` numbers revisions sequentially (`0001_<slug>.py`; `revision_environment`
  makes even plain `alembic revision` connect to the DB) and renders `DecimalString` as
  `sa.String()` so migrations never import app code. SQLite uses batch mode; adding a
  NOT NULL column needs a temporary `server_default` for existing rows.

## Tests

`tests/` mirrors `src/`. `tests/conftest.py` gives `engine` (fresh SQLite migrated with
Alembic, so migrations are exercised) and `client` (`TestClient`). `tests/application/` runs
use cases against an in-memory `FakeUnitOfWork` defined in its `conftest.py`.

## Conventions

- Commits: one-line Conventional Commits (`feat: ...`, `fix(api): ...`), no body, no trailer.
- Ruff line length 100; `allowed-confusables` covers Cyrillic, since UI texts and data are
  Russian. Write a non-breaking space as `" "`, never as a literal character (RUF001).
- UI texts belong in templates, not Python. Code, identifiers and docs are in English.
- `legacy/` (one-off import of an old database) and `data/` are local only: ignored by git,
  excluded from ty and the Docker build.
