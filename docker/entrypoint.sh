#!/bin/sh
# Container entrypoint: everything the image does at start.
#   serve (default)           restore the latest backup if there is no database yet,
#                             apply migrations, then run the server
#   backup [--every SECONDS]  back up the database (and push a dump to GitHub, if configured)
#   backups                   list backups in GitHub
#   restore [OPTIONS]         restore the database (stop the server first)
#   anything else             run as is
set -e

# The database and its copies live in the /data volume.
export KOMMUNALKA_DATABASE_URL="${KOMMUNALKA_DATABASE_URL:-sqlite:////data/kommunalka.db}"
export KOMMUNALKA_BACKUP_DIR="${KOMMUNALKA_BACKUP_DIR:-/data/backups}"

command="${1:-serve}"
[ $# -gt 0 ] && shift

case "$command" in
    serve)
        # A fresh volume gets the data back from GitHub; a failed restore stops the start.
        python -m kommunalka.presentation.cli.restore --if-missing
        # Migrations first, so the server never starts on an outdated schema.
        alembic upgrade head
        exec granian --interface asgi --host 0.0.0.0 --port 8000 kommunalka.presentation.app:app
        ;;
    backup)
        exec python -m kommunalka.presentation.cli.backup "$@"
        ;;
    backups)
        exec python -m kommunalka.presentation.cli.restore --list "$@"
        ;;
    restore)
        exec python -m kommunalka.presentation.cli.restore "$@"
        ;;
    *)
        exec "$command" "$@"
        ;;
esac
