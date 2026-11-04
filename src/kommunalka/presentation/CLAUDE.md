# Presentation

`api/` (JSON, Pydantic schemas), `web/` (Jinja2 pages under `/view/`) and `telegram/` (the bot,
see its `CLAUDE.md`), assembled in `app.py` (entrypoint `kommunalka.presentation.app:app`). `errors.py::describe_error` maps errors
to HTTP codes for both; `app.py` renders HTML errors for `/` and `/view/...`, JSON elsewhere.
Today's date comes from the `TodayDep` dependency (`get_today`, in the `timezone` setting,
`Europe/Kyiv` by default: containers run in UTC), never from `date.today()` in handlers.

Money and readings are sent as JSON strings.

## Web pages

- `web/pages/` turns query results into plain dicts/dataclasses for the templates, one module
  per section (`households`, `bills`, `readings`, `tariffs`; `change` is the comparison of a
  bill with the previous one, shared by two of them), each with its own `router`, joined in
  `pages/__init__.py`. Links are built with
  `url_for` by handler function name, so those names are unique across the package.
  `shared/formatting.py` writes Russian numbers, money, dates and plurals; `shared/messages.py`
  translates the English domain/application error messages by regex — a new error message shown on a page needs
  an entry there.
- UI texts go in templates where possible; sentences built from data are composed in
  `pages/`, error texts in `messages.py`.
- `base.html` builds the menu from the `household` and `section` context values; `/` redirects
  to the overview when there is a single household.
- Static files are linked with a content hash (`asset_version`, cached per process).
  `static/readings.js` (live consumption and bill preview) and `static/bill-share.js` (shares
  the bill PDF through the system share sheet) only enhance pages that work without them;
  sharing files needs HTTPS or localhost.
- The bill PDF (`.../bills/{year}/{month}/pdf`) is a payment slip on landscape A5, drawn on the
  server by `shared/bill_pdf.py` (fpdf2) straight from `queries.BillDetails`: the bill and household
  ids, address and period, then a table of the lines with meter readings and the total as its
  last row; its Russian texts live there. `file_name` (`bill-2026-09.pdf`) names the file for
  both the response and the page's download link. The font is Manrope in `shared/fonts/` (OFL),
  one instance of the variable font per style (regular and bold).

## Shared

`shared/` holds what both the web pages and the bot need: `formatting.py`, `messages.py` and the
bill PDF with its font. It depends on `application` and `domain` only, never on `web/` or
`telegram/`; those two don't import each other either.

## Telegram bot

The bot is a third way into the application next to `api/` and `web/`, built on aiogram. It
long-polls the Bot API as a task of the app's lifespan (no public URL), and starts only when
`KS_BOT_TOKEN` and `KS_ALLOWED_USERS_TG_IDS` are set; `app.py` wires it with a unit-of-work factory.

- `commands.py` — parses command arguments into command objects (`BillCommand`); pure, raises
  `UsageError`. `/bill [YYYY-MM [household]]`: no period means the latest bill; the household
  name is needed only when there are several.
- `handlers.py` — `send_bill(command, uow) -> Reply`: loads data through `application.queries`
  and builds a reply (text, or a PDF with a caption). Synchronous and free of aiogram, so it is
  tested against a database directly.
- `bot.py` — the aiogram part: `create_router` (command routing, access by user id, replies; the
  synchronous handler runs in `asyncio.to_thread`), `BillBot` (polling task) and `create_bot`.
  Access is by the sender's user id: only the users in `KS_ALLOWED_USERS_TG_IDS` (comma
  separated) are answered, in a private chat or a group; others get nothing.
- `texts.py` — the bot's Russian texts. Dates, money and the PDF come from `../shared/`.

A new command: arguments in `commands.py`, the use in `handlers.py`, a route in `bot.py`.
Tests (`tests/presentation/telegram/`) feed updates to a `Dispatcher` with a recording session
instead of the network.
