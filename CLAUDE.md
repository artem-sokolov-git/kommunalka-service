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
make up / make down / make logs       # Docker stack; up and backup get secrets via bws (BWS_PROJECT_ID)
make backup                           # one-off backup container: copy in the volume + dump to GitHub
make backups / make restore            # list dumps in GitHub; restore the latest (args="--revision X")
uv run pytest tests/domain/entities/test_reading.py::test_next_reading_follows_last
```

Run `alembic` from the repo root: its config is `[tool.alembic]` in `pyproject.toml`
(`alembic.ini` only configures logging). Settings live in `src/kommunalka/config.py`
(`Settings`, pydantic-settings): `KOMMUNALKA_`-prefixed environment variables or `.env`,
read through `get_settings()` only at the edges (app factory, migrations `env.py`, backup
CLI). The database URL is `KOMMUNALKA_DATABASE_URL` (default `sqlite:///kommunalka.db`); in
Docker it is `/data/kommunalka.db` in the named volume `data`, not visible on the host: backup
and restore run as one-off containers of the `backup` service (`docker compose run`). Docker
files live in `docker/`: `Dockerfile` (only builds; `Dockerfile.dockerignore` next to it),
`compose.yaml` (`name: kommunalka-service` keeps the volume name; run it through `make`,
which adds `-f docker/compose.yaml` and the root `.env`) and `entrypoint.sh` with all
container start logic (`serve` = restore a missing database from GitHub + migrations +
Granian, the default; `backup`, `backups`, `restore`; container paths).

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
- `presentation/` — `api/` (JSON, Pydantic schemas) and `web/` (Jinja2 pages under `/view/`),
  assembled in `presentation/app.py` (entrypoint `kommunalka.presentation.app:app`).
  `presentation/errors.py::describe_error` maps errors to HTTP codes for both; `app.py`
  renders HTML errors for `/` and `/view/...`, JSON elsewhere. Today's date comes from the
  `TodayDep` dependency (`get_today`, in the `timezone` setting, `Europe/Kyiv` by default:
  containers run in UTC), never from `date.today()` in handlers.

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
- **Combining use cases** in one transaction: put the work in a helper that runs inside an
  already open unit of work (e.g. `use_cases/bills.py::add_bill`), and call it from both use
  cases — `submit_readings_and_issue_bill` saves readings and bills the month they close
  atomically this way.
- **Web pages**: `web/pages.py` turns query results into plain dicts/dataclasses for the
  templates; `formatting.py` writes Russian numbers, money, dates and plurals;
  `messages.py` translates the English domain/application error messages by regex — a new
  error message shown on a page needs an entry there. `base.html` builds the menu from the
  `household` and `section` context values; `/` redirects to the overview when there is a
  single household. Static files are linked with a content hash (`asset_version`, cached
  per process). `static/readings.js` (live consumption and bill preview) and
  `static/bill-card.js` (draws the bill as a PNG and shares or downloads it) only enhance
  pages that work without them; sharing files needs HTTPS or localhost.
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
Alembic, so migrations are exercised) and `client` (`TestClient` with today fixed to
2026-12-31). `tests/application/` runs use cases against an in-memory `FakeUnitOfWork`
defined in its `conftest.py` (a new repository method needs a fake there too).
`tests/presentation/web/conftest.py` sets up a household with a gas meter, readings for
August–October 2026 and bills for August and September through the JSON API.
`tests/infrastructure/conftest.py` runs `FakeGitHub`, an in-process server with the Contents
and commits endpoints, for backup and restore tests (`pythonpath = ["."]` lets tests import
it as `tests.infrastructure.conftest`).

## Conventions

- Commits: one-line Conventional Commits (`feat: ...`, `fix(api): ...`), no body, no trailer.
- Ruff line length 100; `allowed-confusables` covers Cyrillic, since UI texts and data are
  Russian. Write a non-breaking space as `"\u00a0"`, never as a literal character (RUF001).
- UI texts go in templates where possible; sentences built from data are composed in
  `pages.py`, error texts in `messages.py`. Code, identifiers and docs are in English.
- `legacy/` (one-off import of an old database) and `data/` are local only: ignored by git,
  excluded from ty and the Docker build. The volume `data` holds real data: never
  `docker compose down -v`; check pages on a copy (`docker compose -f docker/compose.yaml cp
  api:/data/kommunalka.db <copy>`, then `KOMMUNALKA_DATABASE_URL=sqlite:///<copy>`), never
  change it in place.
