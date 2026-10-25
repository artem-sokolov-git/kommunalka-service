# Tests

`tests/` mirrors `src/`. `conftest.py` starts one PostgreSQL container for the run
(testcontainers, needs Docker) and gives `engine` (an empty database of its own for every test,
migrated with Alembic so migrations are exercised) and `client` (`TestClient` with today fixed
to 2026-12-31).

- `application/` runs use cases against an in-memory `FakeUnitOfWork` defined in its
  `conftest.py` (a new repository method needs a fake there too).
- `presentation/web/conftest.py` sets up a household with a gas meter, readings for
  August–October 2026 and bills for August and September through the JSON API.
