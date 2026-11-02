"""A bill as a PDF: a payment slip on landscape A5, the bill's lines and total as a table."""

from collections.abc import Callable
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import Align, TableBordersLayout, XPos, YPos
from fpdf.fonts import FontFace

from kommunalka.application.queries import BillDetails, BillLineDetails, MeterReadings
from kommunalka.domain import Bill, FixedBillLine, MeteredBillLine, Reading
from kommunalka.presentation.web.formatting import money, month_name, number, unit_label

FONT = Path(__file__).parent / "fonts" / "Manrope[wght].ttf"
FAMILY = "Manrope"

PAGE = (148, 210)  # A5, mm: fpdf2 warns about the "A5" name, its size changed in 2.8.5
MARGIN = 12
LABEL_WIDTH = 32
COLUMNS = {  # mm, 186 in all: the landscape page width without the margins
    "Услуга": 66,
    "Было": 24,
    "Стало": 24,
    "Кол-во": 18,
    "Тариф, грн": 26,
    "Сумма, грн": 28,
}
ALIGN = ("LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT")
NONE = "—"

INK = (22, 25, 29)
MUTED = (95, 102, 112)
RULE = (190, 188, 180)
TOTAL = FontFace(emphasis="BOLD", size_pt=10, color=INK)


def file_name(bill: Bill) -> str:
    """`kommunalka-2026-09-<bill id>.pdf`: the month for people, the id to tell bills apart."""
    return f"kommunalka-{bill.period_start:%Y-%m}-{bill.id}.pdf"


def render_bill(details: BillDetails) -> bytes:
    bill, household = details.bill, details.household
    title = f"Счёт за {month_name(bill.period_start.month)} {bill.period_start.year}"
    pdf = FPDF(orientation="landscape", format=PAGE)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=True, margin=MARGIN)
    pdf.c_margin = 0  # the heading lines up with the table's edges
    pdf.add_font(FAMILY, "", FONT, variations={"wght": 400})
    pdf.add_font(FAMILY, "B", FONT, variations={"wght": 700})
    pdf.set_title(f"{title} · {household.name}")
    pdf.set_creator("Коммуналка")
    pdf.add_page()

    pdf.set_text_color(*INK)
    pdf.set_font(FAMILY, "B", 13)
    pdf.cell(pdf.epw * 0.4, 7, title)
    pdf.set_font(FAMILY, "B", 10)
    pdf.cell(0, 7, f"№ {bill.id}", align=Align.R)
    pdf.ln(10)
    pdf.set_font(FAMILY, size=9)
    for label, value in (
        ("Домохозяйство", household.name),
        ("№ домохозяйства", str(household.id)),
        ("Адрес", household.address),
        ("Период", f"{bill.period_start:%d.%m.%Y} — {bill.period_end:%d.%m.%Y}"),
    ):
        pdf.set_text_color(*MUTED)
        pdf.cell(LABEL_WIDTH, 5, f"{label}:")
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 5, value, align=Align.L, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(5)
    pdf.set_font(FAMILY, size=8)
    pdf.set_draw_color(*RULE)
    with pdf.table(
        width=pdf.epw,
        col_widths=tuple(COLUMNS.values()),
        text_align=ALIGN,
        borders_layout=TableBordersLayout.HORIZONTAL_LINES,
        headings_style=FontFace(emphasis="BOLD", color=MUTED),
        line_height=4.5,
        padding=(1.5, 1),
    ) as table:
        table.row(tuple(COLUMNS))
        for line in details.lines:
            table.row(_cells(line))
        total = table.row()
        total.cell("Итого к оплате", colspan=len(COLUMNS) - 1, align=Align.R, style=TOTAL)
        total.cell(money(bill.total), align=Align.R, style=TOTAL)
    return bytes(pdf.output())


def _cells(details: BillLineDetails) -> tuple[str, ...]:
    line, service = details.line, details.service
    match line:
        case FixedBillLine():
            return (service.name, NONE, NONE, NONE, NONE, money(line.amount))
        case MeteredBillLine():
            readings = details.readings
            return (
                f"{service.name}, {unit_label(service.unit)}",
                _values(readings, lambda r: r.previous) or NONE,
                _values(readings, lambda r: r.current) or NONE,
                number(line.quantity),
                money(line.price),
                money(line.amount),
            )


def _values(readings: list[MeterReadings], pick: Callable[[MeterReadings], Reading | None]) -> str:
    """A reading of each meter, one per line; meters are named when there are several."""
    named = len(readings) > 1
    return "\n".join(
        (f"{r.meter.label}: " if named else "")
        + (number(reading.value) if (reading := pick(r)) else NONE)
        for r in readings
    )
