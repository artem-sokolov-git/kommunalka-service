# syntax=docker/dockerfile:1

FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


FROM python:3.13-slim

RUN groupadd --system app \
    && useradd --system --gid app --no-create-home app \
    && mkdir /data \
    && chown app:app /data

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
# Alembic reads its config from the working directory.
COPY pyproject.toml alembic.ini ./
COPY docker/entrypoint.sh /usr/local/bin/entrypoint

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app
VOLUME /data
EXPOSE 8000

ENTRYPOINT ["entrypoint"]
CMD ["serve"]
