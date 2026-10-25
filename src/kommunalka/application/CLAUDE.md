# Application

`UnitOfWork` and repository `Protocol`s (ports), use cases in `use_cases/` (write) and
`queries.py` (read, including read models for pages). Use cases only load data, call the domain
and save; business rules belong in `domain/`.

- **Unit of work**: every use case/query is one `with uow:` block = one connection and
  transaction; leaving it without `commit()` rolls back. Don't call another query/use case
  inside a `with uow:` block — re-entering opens a new connection; use repositories directly.
- **Uniqueness** is checked twice: by `ensure_*` functions in use cases (readable errors) and by
  DB unique constraints (races). Tariff overlap has no DB constraint.
- **Combining use cases** in one transaction: put the work in a helper that runs inside an
  already open unit of work (e.g. `use_cases/bills.py::add_bill`), and call it from both use
  cases — `submit_readings_and_issue_bill` saves readings and bills the month they close
  atomically this way.
- A new repository method needs a fake in `tests/application/conftest.py` (`FakeUnitOfWork`).
