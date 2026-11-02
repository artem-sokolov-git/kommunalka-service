"""HTML pages for people, on top of the same application queries as the JSON API."""

from fastapi import APIRouter

from kommunalka.presentation.web.pages import bills, households, readings, tariffs

router = APIRouter(include_in_schema=False)
for module in (households, bills, readings, tariffs):
    router.include_router(module.router)
