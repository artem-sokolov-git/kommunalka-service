# Presentation

`api/` (JSON, Pydantic schemas) and `web/` (Jinja2 pages under `/view/`), assembled in
`app.py` (entrypoint `kommunalka.presentation.app:app`). `errors.py::describe_error` maps errors
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
  `formatting.py` writes Russian numbers, money, dates and plurals; `messages.py` translates the
  English domain/application error messages by regex — a new error message shown on a page needs
  an entry there.
- UI texts go in templates where possible; sentences built from data are composed in
  `pages/`, error texts in `messages.py`.
- `base.html` builds the menu from the `household` and `section` context values; `/` redirects
  to the overview when there is a single household.
- Static files are linked with a content hash (`asset_version`, cached per process).
  `static/readings.js` (live consumption and bill preview) and `static/bill-share.js` (the
  bill's «Отправить» button opens the system share sheet with the PDF; without file sharing the
  button is a menu: Telegram and mail links with the total as text, and the PDF download) only enhance pages that work without them;
  sharing files needs HTTPS or localhost.
- The bill PDF (`.../bills/{year}/{month}/pdf`) is a payment slip on landscape A5, drawn on the
  server by `bill_pdf.py` (fpdf2) straight from `queries.BillDetails`: the bill and household
  ids, address and period, then a table of the lines with meter readings and the total as its
  last row; its Russian texts live there. `file_name` (month and bill id) names the file for
  both the response and the page's download link. The font is Manrope in `web/fonts/` (OFL),
  one instance of the variable font per style (regular and bold).
