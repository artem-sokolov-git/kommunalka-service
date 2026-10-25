# Kommunalka Service

Simple service for tracking utility bills: meters, monthly readings, tariffs and bills
of a household.

Python 3.13, FastAPI on Granian, PostgreSQL via SQLAlchemy Core, Alembic migrations.

## Run

The app runs only in Docker.

```sh
printf '\nKS_PG_PASS=%s\n' "$(openssl rand -hex 16)" >> .env   # once: the database password
make up      # build locally and start in Docker: http://localhost:8000
make down    # stop
make backup  # dump the database now into ./backups
```

Settings are taken from the environment or `.env` (ignored by git). `KS_PG_PASS` is required:
letters and digits only (it is also a part of the database URL, and Compose reads `$` as a
variable). It is applied when the database is created, so set it before the first `make up`.

### Deploy

`.github/workflows/image.yml` builds the image on every push to `main` and publishes it to the
private package `ghcr.io/artem-sokolov-git/kommunalka-service` (`latest` and `sha-<commit>`;
amd64 and arm64). `docker/compose.yaml` alone pulls it (`pull_policy: always`), so a deploy
tool needs only that file, with `KS_PG_PASS` in the environment of the stack; the host logs in
to the registry once: `docker login ghcr.io -u artem-sokolov-git` with a classic token that
has `read:packages`. `make` adds `docker/compose.build.yaml` and builds from the working tree
instead.

The pages are at http://localhost:8000, the API docs at `/docs`.

- **Обзор** (opens first when there is one household; all of them are at
  `/view/households`) tells what to do this month: submit readings, issue a pending bill,
  or nothing until the next readings. It also shows the last bill against the previous
  month and a chart of the last 12 bills.
- **Показания**: each month, enter the meter values; consumption and a preview of the
  bill are shown as you type. "Сохранить и выставить счёт" saves the readings and issues
  the bill for the previous month at once, with the gas transportation amount from the
  supplier's receipt. A mistyped reading can be corrected until its month is billed.
- **Счета**: bills by year; a bill shows each service with its readings and the change
  against the previous month. "Поделиться" turns the bill into a picture for Telegram or
  any other app; browsers share files only over HTTPS or on localhost, elsewhere the
  picture is downloaded.
- **Тарифы**: current prices with their history; a new price starts from a chosen month
  and can be undone until a bill uses it.

Migrations are applied on start. The database lives in the Docker volume `kommunalka-pg`,
not on the host, and is kept between restarts; `docker compose down -v` would delete it.
Set `KOMMUNALKA_PORT` if 8000 is busy.

Other settings have defaults, see `src/kommunalka/infrastructure/config/settings.py`: the
database URL (`KS_DATABASE_URL`, set by the compose file) and `KS_TIMEZONE` (`Europe/Kyiv`,
decides which day it is).

### Backups

The `backup` service is the image
[postgres-backup-local](https://github.com/prodrigestivill/docker-postgres-backup-local): it
runs `pg_dump` daily (and on start) and writes the dumps to `./backups` in the root of the
project, ignored by git, keeping the last 7 days, 4 weeks and 6 months. `make backup` makes
one now; `make logs` shows the schedule at work. The dumps are on the same machine as the
database: copy `backups/` elsewhere if you need protection from losing the disk. When the
stack is deployed from `docker/compose.yaml` alone, `./backups` is next to the copied
`docker/` folder.

### Restore

`make restore` stops the app, loads the latest dump into the database (in a single
transaction, so a failed restore changes nothing) and starts the stack again.

```sh
make backups                                   # list dumps
make restore file=daily/kommunalka-20261025.sql.gz   # a specific one
```

A new volume starts with an empty database: on a new machine copy `backups/` there, run
`make up` and then `make restore`. A dump made before the migrations were renamed holds an
old version number: run `alembic stamp head` after restoring it.

### Moving from SQLite

The data of the previous, SQLite version is copied once into an empty, migrated PostgreSQL by
`legacy/sqlite_import.py` (a local file, not in git). The SQLite volume is mounted read-only
and its revision must be `0008`; the script refuses a non-empty target and checks the row
counts before it commits.

```sh
docker compose -f docker/compose.yaml -f docker/compose.build.yaml --env-file .env run --rm --no-deps \
  -v ./legacy:/legacy:ro -v kommunalka-data:/sqlite:ro app python /legacy/sqlite_import.py /sqlite/kommunalka.db
```

## Develop

```sh
make setup                       # dependencies and pre-commit hooks
make check                       # ruff, ty and tests (the tests start PostgreSQL in Docker)
make migration name=add_notes    # migration from model changes
```

The app is not run on the host: use `make up`. `make migration` starts a throwaway PostgreSQL
container for the comparison of the models with the migrations. Run `make` for all commands.

## How billing works

- A reading taken in a month closes the previous one: a reading on October 1–5 is
  for September. One reading per meter and month; the first reading of a meter
  is a baseline.
- A tariff is valid from `valid_from` to `valid_to`, or open-ended without it.
  For a metered service the price is per unit, for an unmetered one (e.g. gas
  transportation) it is a monthly amount.
- A new price ("Тарифы" page or `POST /services/{id}/prices`) starts on the first
  day of a month, after the current one, and closes the current price the day
  before. It can't start in a month that is already billed. The latest price can
  be undone (`DELETE /services/{id}/prices/latest`) until a bill uses it.
- A bill covers one calendar month: consumption × tariff for each metered
  service, plus monthly amounts of unmetered services; a ready amount from the
  supplier can be entered instead when issuing the bill (`fixed_amounts`), the
  tariff stays as it is. The readings page can save the readings and issue the
  bill of the month they close at once. Once a month is billed, its readings
  can't be changed.

## API

| Method | Path | |
|---|---|---|
| `POST`, `GET` | `/households` | register, list |
| `GET` | `/households/{id}` | get |
| `POST`, `GET` | `/households/{id}/meters` | install a meter, list |
| `POST` | `/meters/{id}/removal` | remove a meter |
| `POST`, `GET` | `/meters/{id}/readings` | submit a reading, list |
| `PATCH` | `/readings/{id}` | correct a reading of an unbilled month |
| `POST`, `GET` | `/services` | add a service, list |
| `POST`, `GET` | `/services/{id}/tariffs` | set a tariff period, list |
| `POST` | `/services/{id}/prices` | change the price from a month |
| `DELETE` | `/services/{id}/prices/latest` | undo the latest price |
| `POST`, `GET` | `/households/{id}/bills` | issue a bill for a month, list |
| `GET` | `/households/{id}/bills/{year}/{month}` | get a bill |

Money and readings are decimal strings in JSON. Errors: 404 not found,
409 conflict (duplicate, overlapping tariff, billed month), 422 rule violation.

```sh
curl -X POST localhost:8000/meters/$METER/readings \
  -H 'content-type: application/json' -d '{"value": "41768", "taken_on": "2026-10-01"}'
curl -X POST localhost:8000/households/$HOUSEHOLD/bills \
  -H 'content-type: application/json' -d '{"year": 2026, "month": 9}'
```

## Layout

```
src/kommunalka/
├── domain/           entities, value objects, bill calculation
├── application/      use cases, queries, repository and unit of work protocols
├── infrastructure/   PostgreSQL repositories, unit of work, migrations
└── presentation/
    ├── api/          JSON API: routers, schemas, error mapping
    ├── web/          HTML pages: overview, readings, bills, tariffs
    └── app.py        assembles the API and the pages into one app
docker/               Dockerfile, compose.yaml, compose.build.yaml (run through make)
```
