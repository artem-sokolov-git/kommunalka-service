# Presentation

`api/` (JSON, Pydantic schemas) and `web/` (Jinja2 pages under `/view/`), assembled in
`app.py` (entrypoint `kommunalka.presentation.app:app`). `errors.py::describe_error` maps errors
to HTTP codes for both; `app.py` renders HTML errors for `/` and `/view/...`, JSON elsewhere.
Today's date comes from the `TodayDep` dependency (`get_today`, in the `timezone` setting,
`Europe/Kyiv` by default: containers run in UTC), never from `date.today()` in handlers.

Money and readings are sent as JSON strings.

## Web pages

- `web/pages.py` turns query results into plain dicts/dataclasses for the templates;
  `formatting.py` writes Russian numbers, money, dates and plurals; `messages.py` translates the
  English domain/application error messages by regex — a new error message shown on a page needs
  an entry there.
- UI texts go in templates where possible; sentences built from data are composed in
  `pages.py`, error texts in `messages.py`.
- `base.html` builds the menu from the `household` and `section` context values; `/` redirects
  to the overview when there is a single household.
- Static files are linked with a content hash (`asset_version`, cached per process).
  `static/readings.js` (live consumption and bill preview) and `static/bill-card.js` (draws the
  bill as a PNG and shares or downloads it) only enhance pages that work without them; sharing
  files needs HTTPS or localhost.
