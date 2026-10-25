# Database

Table models are `DeclarativeBase` classes used **only** as schema and query targets through
`Connection`; repositories map rows to domain objects by hand. `SqlUnitOfWork` translates
`IntegrityError` into `application.exceptions.ConflictError`.

Money and readings are stored as `NUMERIC` without precision (a value keeps the scale it was
written with). Bill line order is kept in `bill_lines.position`.

## Migrations

They live in `migrations/` (`script_location` is a package path). `env.py` numbers revisions
sequentially (`0001_<slug>.py`; `revision_environment` makes even plain `alembic revision`
connect to the DB); there is one migration per table. Create them with `make migration`: it
starts a throwaway PostgreSQL for the comparison of the models with the migrations. Adding a
NOT NULL column needs a temporary `server_default` for existing rows. A database restored from
a dump made before a migration was renamed or merged needs `alembic stamp head`.
