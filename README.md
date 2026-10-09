# Kommunalka Service

Simple service for tracking utility bills: meters, monthly readings, tariffs and bills
of a household.

Python 3.13, FastAPI on Granian, SQLite via SQLAlchemy Core, Alembic migrations.

## Run

```sh
make up      # build and start in Docker: http://localhost:8000
make down    # stop
make backup  # back up now: data/backups/ and a dump pushed to GitHub
```

`make up` takes secrets from a [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/)
project through `bws run`: install `bws`, set `BWS_ACCESS_TOKEN` of a machine account with
access to the project in the environment, and put the project id into `.env` (ignored by
git) as `BWS_PROJECT_ID`.

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

Migrations are applied on start. The database is a plain file on the host,
`data/kommunalka.db`, kept between restarts. The `backup` service copies it into
`data/backups/` on start and daily, keeping the 30 newest. To restore a backup: `make down`,
copy it over `data/kommunalka.db`, `make up`. Set `KOMMUNALKA_PORT` if 8000 is busy.

Settings are `KOMMUNALKA_`-prefixed environment variables (or `.env`), see
`src/kommunalka/config.py`: the database URL, `KOMMUNALKA_TIMEZONE` (`Europe/Kyiv`, decides
which day it is), and the backup directory, number of copies, interval and git repository.

### Backups in a private GitHub repository

The `backup` service can also push a text dump of the database, `kommunalka.sql`, to a
git repository on each run; a new commit appears only when the data changed, so the
repository history is the history of backups.

1. Create an empty private repository: `gh repo create kommunalka-backups --private`.
2. Create a [fine-grained token](https://github.com/settings/personal-access-tokens/new)
   with access to that repository only and the "Contents: Read and write" permission.
3. Add both to the Bitwarden project as secrets `KOMMUNALKA_DB_BACKUP_REPO_URL`
   (`https://github.com/<you>/kommunalka-backups.git`) and `KOMMUNALKA_BACKUP_GITHUB_TOKEN`
   (`github_pat_...`).
4. `make up`; `docker compose logs backup` shows `...kommunalka-backups.git: pushed`.

To restore from the repository: `make down`, move `data/kommunalka.db` aside, then
`sqlite3 data/kommunalka.db < kommunalka.sql` with the dump from a clone, and `make up`.

## Develop

```sh
make install                     # dependencies and pre-commit hooks
make dev                         # API with reload on http://localhost:8000
make check                       # ruff, ty and tests
make migration name=add_notes    # migration from model changes
```

Local runs use `./kommunalka.db`, separate from the Docker one. Override with
`KOMMUNALKA_DATABASE_URL`. Run `make` for all commands.

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
├── infrastructure/   SQLite repositories, unit of work, migrations
└── presentation/
    ├── api/          JSON API: routers, schemas, error mapping
    ├── web/          HTML pages: overview, readings, bills, tariffs
    └── app.py        assembles the API and the pages into one app
```
