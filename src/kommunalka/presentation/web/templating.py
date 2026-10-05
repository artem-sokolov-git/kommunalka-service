import hashlib
from functools import cache
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

STATIC_DIR = Path(__file__).parent / "static"


@cache
def asset_version(path: str) -> str:
    """Short hash of a static file: a changed file gets a new URL, so browsers drop the old one."""
    return hashlib.sha256((STATIC_DIR / path).read_bytes()).hexdigest()[:10]


def _assets(_request: Request) -> dict[str, Any]:
    return {"asset_version": asset_version}


templates = Jinja2Templates(
    directory=Path(__file__).parent / "templates", context_processors=[_assets]
)
