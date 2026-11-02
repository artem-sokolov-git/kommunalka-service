"""A bill as a PDF: the same content as the bill page, laid out on one A4 sheet."""

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF
from fpdf.enums import Align, XPos, YPos

from kommunalka.presentation.web.formatting import long_date, month_name

if TYPE_CHECKING:
    from kommunalka.presentation.web.pages.bills import BillView, LineView

FONT = Path(__file__).parent / "fonts" / "Manrope[wght].ttf"
# fpdf2 knows only regular and bold styles of a family, so the heaviest weight is a family.
TEXT, HEAVY = "Manrope", "Manrope-XB"

MARGIN = 20
AMOUNT_WIDTH = 40
ROW_HEIGHT = 22

INK = (22, 25, 29)
MUTED = (95, 102, 112)
RULE = (227, 225, 218)
ACCENT = (29, 95, 180)
CHANGE_COLORS = {
    "down": ((227, 241, 232), (35, 96, 60)),
    "up": ((255, 244, 229), (154, 77, 0)),
    "same": ((244, 243, 239), (95, 102, 112)),
}


def render_bill(view: "BillView", today: date) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=True, margin=MARGIN)
    pdf.c_margin = 0  # text starts and ends flush with the rules and the pill
    pdf.add_font(TEXT, "", FONT, variations={"wght": 500})
    pdf.add_font(TEXT, "B", FONT, variations={"wght": 700})
    pdf.add_font(HEAVY, "", FONT, variations={"wght": 800})
    title = f"Счёт за {month_name(view.month)} {view.year}"
    pdf.set_title(f"{title} · {view.household.name}")
    pdf.set_creator("Коммуналка")
    pdf.add_page()
    width = pdf.epw

    pdf.set_font(HEAVY, size=18)
    pdf.set_text_color(*INK)
    pdf.cell(width / 2, 10, "Коммуналка")
    pdf.set_font(TEXT, size=11)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 10, view.household.name, align=Align.R, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.multi_cell(0, 5, view.household.address, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(10)
    pdf.set_font(TEXT, "B", 14)
    pdf.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font(HEAVY, size=40)
    pdf.set_text_color(*INK)
    pdf.cell(pdf.get_string_width(view.total) + 2, 20, view.total)
    pdf.set_font(TEXT, "B", 18)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 20, "грн", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if view.change:
        fill, ink = CHANGE_COLORS[view.change.direction]
        pdf.set_font(TEXT, "B", 10)
        pill = pdf.get_string_width(view.change.text) + 10
        pdf.set_fill_color(*fill)
        pdf.set_text_color(*ink)
        pdf.rect(pdf.get_x(), pdf.get_y(), pill, 8, style="F", round_corners=True, corner_radius=4)
        pdf.cell(pill, 8, view.change.text, align=Align.C)
        pdf.ln(12)
    else:
        pdf.ln(4)

    pdf.set_draw_color(*RULE)
    pdf.line(MARGIN, pdf.get_y(), MARGIN + width, pdf.get_y())
    pdf.ln(2)

    for line in view.lines:
        _row(pdf, line)

    pdf.set_font(TEXT, size=8)
    pdf.set_text_color(*MUTED)
    pdf.ln(4)
    pdf.cell(0, 5, f"Сформировано {long_date(today)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


def _row(pdf: FPDF, line: "LineView") -> None:
    if pdf.will_page_break(ROW_HEIGHT):
        pdf.add_page()
    left, top = pdf.l_margin, pdf.get_y() + 3
    text_width = pdf.epw - AMOUNT_WIDTH

    pdf.set_xy(left, top)
    pdf.set_font(TEXT, "B", 12)
    pdf.set_text_color(*INK)
    pdf.multi_cell(text_width, 6, line.service, align=Align.L, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(TEXT, size=9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(text_width, 5, _detail(line), align=Align.L, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    bottom = pdf.get_y() + 3

    pdf.set_xy(left + text_width, top)
    pdf.set_font(TEXT, "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(AMOUNT_WIDTH, 6, line.amount, align=Align.R)
    if line.change:
        pdf.set_xy(left + text_width, top + 6)
        pdf.set_font(TEXT, size=8)
        pdf.set_text_color(*MUTED)
        pdf.cell(AMOUNT_WIDTH, 5, line.change, align=Align.R)

    pdf.set_draw_color(*RULE)
    pdf.line(left, bottom, left + pdf.epw, bottom)
    pdf.set_xy(left, bottom)


def _detail(line: "LineView") -> str:
    if not line.quantity:
        return "сумма за месяц"
    used = f"{line.quantity} \u00d7 {line.price}"
    return f"{line.readings} · {used}" if line.readings else used
