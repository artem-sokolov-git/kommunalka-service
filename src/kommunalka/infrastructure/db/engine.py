from sqlalchemy import Engine, create_engine


def create_db_engine(url: str) -> Engine:
    # Pooled connections die when the database restarts: check them before use.
    return create_engine(url, pool_pre_ping=True)
