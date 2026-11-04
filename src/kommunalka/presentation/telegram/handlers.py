"""What the bot does for a command: loads data through queries and builds a reply."""

from dataclasses import dataclass
from datetime import date

from kommunalka.application import queries
from kommunalka.application.exceptions import NotFoundError
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.presentation.shared.bill_pdf import file_name, render_bill
from kommunalka.presentation.shared.formatting import month_name
from kommunalka.presentation.shared.messages import translate
from kommunalka.presentation.telegram import texts
from kommunalka.presentation.telegram.commands import BillCommand


@dataclass(frozen=True)
class Reply:
    """A text, or a PDF (`document`) with the text as its caption."""

    text: str
    file_name: str | None = None
    document: bytes | None = None


def send_bill(command: BillCommand, uow: UnitOfWork) -> Reply:
    households = queries.list_households(uow)
    if command.household is not None:
        wanted = command.household.casefold()
        households = [h for h in households if h.name.casefold() == wanted]
    if not households:
        return Reply(texts.NO_HOUSEHOLD)
    if len(households) > 1:
        return Reply(texts.several_households([h.name for h in households]))
    household = households[0]
    try:
        if command.year is None or command.month is None:
            bills = queries.list_bills(uow, household.id)
            if not bills:
                return Reply(texts.NO_BILLS)
            period = max(bill.period_start for bill in bills)
        else:
            period = date(command.year, command.month, 1)
        details = queries.bill_details(uow, household.id, period.year, period.month)
    except NotFoundError as error:
        return Reply(translate(str(error)).capitalize() + ".")
    caption = texts.caption(month_name(period.month), period.year, household.name)
    return Reply(caption, file_name(details.bill), render_bill(details))
