import pytest
from sqlalchemy import Engine

from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork
from kommunalka.presentation.telegram.commands import BillCommand
from kommunalka.presentation.telegram.handlers import send_bill

pytestmark = pytest.mark.usefixtures("household")


def test_sends_the_pdf_of_the_month(engine: Engine) -> None:
    reply = send_bill(BillCommand(2026, 9), SqlUnitOfWork(engine))

    assert reply.file_name == "bill-2026-09.pdf"
    assert reply.document and reply.document.startswith(b"%PDF-")
    assert reply.text == "Счёт за сентябрь 2026 · Дом <b>"


def test_without_a_month_sends_the_latest_bill(engine: Engine) -> None:
    reply = send_bill(BillCommand(), SqlUnitOfWork(engine))

    assert reply.file_name == "bill-2026-09.pdf"


def test_explains_an_unbilled_month(engine: Engine) -> None:
    reply = send_bill(BillCommand(2026, 10), SqlUnitOfWork(engine))

    assert reply.document is None
    assert reply.text == "Счёт за октябрь 2026 не найден."


def test_household_is_found_by_name_ignoring_case(engine: Engine) -> None:
    reply = send_bill(BillCommand(2026, 9, "дом <B>"), SqlUnitOfWork(engine))

    assert reply.document


def test_unknown_household(engine: Engine) -> None:
    reply = send_bill(BillCommand(2026, 9, "Дача"), SqlUnitOfWork(engine))

    assert reply.text == "Домохозяйство не найдено."
