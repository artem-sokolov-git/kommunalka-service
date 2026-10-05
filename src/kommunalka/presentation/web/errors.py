from fastapi import Request
from fastapi.responses import HTMLResponse

from kommunalka.presentation.web.messages import translate
from kommunalka.presentation.web.templating import templates


def is_page_request(request: Request) -> bool:
    path = request.url.path
    return path == "/" or path.startswith("/view/")


def error_page(request: Request, code: int, detail: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "error.html", {"code": code, "detail": translate(detail)}, status_code=code
    )
