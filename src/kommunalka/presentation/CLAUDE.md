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
  `static/readings.js` (live consumption and bill preview) and `static/bill-share.js` (shares
  the bill PDF through the system share sheet) only enhance pages that work without them;
  sharing files needs HTTPS or localhost.
- The bill PDF (`.../bills/{year}/{month}/pdf`) is drawn on the server by `bill_pdf.py` (fpdf2)
  from the same `BillView` as the page; its Russian texts live there. The font is Manrope in
  `web/fonts/` (OFL), registered once per weight: fpdf2 has no weights beyond regular and bold.
