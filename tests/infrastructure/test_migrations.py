from alembic import command
from alembic.config import Config


def test_migrations_match_models(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")

    command.check(alembic_config)


def test_migrations_downgrade_to_base(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")

    command.downgrade(alembic_config, "base")
