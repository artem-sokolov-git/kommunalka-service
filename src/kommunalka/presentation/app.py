"""Application assembly: the JSON API and the HTML pages over one database."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine
from starlette.exceptions import HTTPException

from kommunalka.config import get_settings
from kommunalka.infrastructure.db.engine import create_db_engine
from kommunalka.presentation.api.routers import households, meters, readings, services
from kommunalka.presentation.errors import HANDLED_ERRORS, describe_error
from kommunalka.presentation.web import pages
from kommunalka.presentation.web.errors import error_page, is_page_request
from kommunalka.presentation.web.templating import STATIC_DIR


def create_app(engine: Engine | None = None) -> FastAPI:
    """Build the app; the database must already be migrated (`alembic upgrade head`)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = engine or create_db_engine(get_settings().database_url)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Kommunalka", lifespan=lifespan)
    for module in (households, services, meters, readings):
        app.include_router(module.router)
    app.include_router(pages.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    for error in HANDLED_ERRORS:
        app.add_exception_handler(error, _handle_error)
    app.add_exception_handler(HTTPException, _handle_http_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    return app


async def _handle_error(request: Request, exc: Exception) -> Response:
    code, detail = describe_error(exc)
    if is_page_request(request):
        return error_page(request, code, detail)
    return JSONResponse({"detail": detail}, status_code=code)


async def _handle_http_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, HTTPException)
    if is_page_request(request):
        return error_page(request, exc.status_code, str(exc.detail))
    return await http_exception_handler(request, exc)


async def _handle_validation_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    if is_page_request(request):
        # A malformed page URL, e.g. month 13, is a page that doesn't exist.
        return error_page(request, 404, "Страница не найдена")
    return await request_validation_exception_handler(request, exc)


app = create_app()
