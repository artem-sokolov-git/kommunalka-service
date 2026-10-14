# Docker

In Docker the database is `/data/kommunalka.db` in the named volume `data` (Docker name
`kommunalka-data`, set in `compose.yaml`; the older `kommunalka-service_data` is unused), not
visible on the host. Backups are not part of the code: the `backup` service is the external image
`sqlite-repo-backuper` (daily release in a private GitHub repo; the token is
`GH_TOKEN` from the environment or the git-ignored `.env`); backup, list and restore run as
one-off containers of it (`docker compose run`). It runs as uid 999, the `app` user of the
image. Docker files live in `docker/`: `Dockerfile` (builds the image; its `CMD` applies
migrations and starts Granian, the database path is set there; `Dockerfile.dockerignore` next
to it) and `compose.yaml` (run it through `make`, which adds `-f docker/compose.yaml`,
`-f docker/compose.build.yaml` and the root `.env` for variable substitution only).
`compose.yaml` alone is what a deploy tool (Dockhand) uses: it copies only `docker/`, so
the app image is not built there but pulled from the private `ghcr.io/artem-sokolov-git/
kommunalka-service`, published by `.github/workflows/image.yml` on every push to `main`;
`compose.build.yaml` swaps that for a local build.
