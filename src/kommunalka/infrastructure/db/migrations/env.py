from collections.abc import Iterable
from logging.config import fileConfig
from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from alembic.operations.ops import MigrationScript
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, pool

from kommunalka.config import get_settings
from kommunalka.infrastructure.db.models import Base, DecimalString

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)
url = config.get_main_option("sqlalchemy.url") or get_settings().database_url


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    """Render app column types by their storage type, so migrations don't import app code."""
    if type_ == "type" and isinstance(obj, DecimalString):
        return "sa.String()"
    return False


def number_revision(
    _context: MigrationContext,
    _revision: str | Iterable[str | None] | Iterable[str],
    directives: list[MigrationScript],
) -> None:
    """Give new revisions sequential ids: 0001, 0002, ..."""
    head = ScriptDirectory.from_config(config).get_current_head()
    directives[0].rev_id = f"{int(head) + 1:04d}" if head else "0001"


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        render_item=render_item,
        process_revision_directives=number_revision,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            # SQLite can't ALTER most things, so changes are made by recreating tables.
            render_as_batch=True,
            render_item=render_item,
            process_revision_directives=number_revision,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
