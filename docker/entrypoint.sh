#!/bin/sh
# Container entrypoint: everything the image does at start.
#   serve (default)  apply migrations, then run the server
#   anything else    run as is
set -e

# The database lives in the /data volume.
export KOMMUNALKA_DATABASE_URL="${KOMMUNALKA_DATABASE_URL:-sqlite:////data/kommunalka.db}"

command="${1:-serve}"
[ $# -gt 0 ] && shift

case "$command" in
    serve)
        # Migrations first, so the server never starts on an outdated schema.
        alembic upgrade head
        exec granian --interface asgi --host 0.0.0.0 --port 8000 kommunalka.presentation.app:app
        ;;
    *)
        exec "$command" "$@"
        ;;
esac
