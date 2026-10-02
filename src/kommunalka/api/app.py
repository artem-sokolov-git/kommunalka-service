from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from kommunalka.api.errors import register_error_handlers
from kommunalka.api.routers import households, meters, readings, services
from kommunalka.infrastructure.db.engine import create_db_engine, database_url


def create_app(engine: Engine | None = None) -> FastAPI:
    """Build the app; the database must already be migrated (`alembic upgrade head`)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = engine or create_db_engine(database_url())
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Kommunalka", lifespan=lifespan)
    register_error_handlers(app)
    for module in (households, services, meters, readings):
        app.include_router(module.router)
    return app


app = create_app()
