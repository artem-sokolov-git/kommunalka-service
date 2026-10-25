# Docker

In Docker the database is the `db` service (`postgres:18.6`) with the named volume `pg` (Docker
name `kommunalka-pg`, set in `compose.yaml`), not visible on the host. Its password is
`KS_PG_PASS` from the environment or the git-ignored `.env`: letters and digits only, since it is
also a part of the URL of the app (`KS_DATABASE_URL`), and no `$` (Compose would read it as a
variable). The password is set when the volume is created; to change it, remove the volume
(only while it holds no data). The volume `kommunalka-data` is the old SQLite database, unused
now; the older `kommunalka-service_data` is unused too.

Backups are not part of the code: the `backup` service is the external image
`postgres-backup-local` (a `pg_dump` daily and on start, kept 7 days, 4 weeks and 6 months),
writing to `./backups` in the root of the project (`../backups` in `compose.yaml`; ignored by
git and by the Docker build). It runs as root, because a new directory belongs to root and the
image's `postgres` user could not write to it, and it has its own healthcheck, since the image
checks only every 5 minutes and `up --wait` would wait as long. Backup, list and restore run
as one-off containers of it (`docker compose run`); the image's entrypoint is `/init.sh`, so a
shell command is passed as `sh -c '...'`. A dump holds the migration version it was made at:
after restoring one made before a migration was renamed or merged, run `alembic stamp head`.

Docker files live in `docker/`: `Dockerfile` (builds the image; its `CMD` applies migrations
and starts Granian, the database URL comes from the compose file; `Dockerfile.dockerignore`
next to it) and `compose.yaml` (run it through `make`, which adds `-f docker/compose.yaml`,
`-f docker/compose.build.yaml` and the root `.env` for variable substitution only).
`compose.yaml` alone is what a deploy tool (Dockhand) uses: it copies only `docker/`, so
the app image is not built there but pulled from the private `ghcr.io/artem-sokolov-git/
kommunalka-service`, published by `.github/workflows/image.yml` on every push to `main`;
`compose.build.yaml` swaps that for a local build. There `../backups` points next to the
copied `docker/`, not into the project.

The old SQLite database is copied into PostgreSQL once by `legacy/sqlite_import.py` (the
target must be migrated and empty; the SQLite volume is mounted read-only):

```sh
docker compose -f docker/compose.yaml -f docker/compose.build.yaml --env-file .env run --rm --no-deps \
  -v ./legacy:/legacy:ro -v kommunalka-data:/sqlite:ro app python /legacy/sqlite_import.py /sqlite/kommunalka.db
```
