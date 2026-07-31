"""Alembic environment: wired to the app's models and config.yaml URL."""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# Make the repo root importable when alembic runs from anywhere.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.config import load_config  # noqa: E402
from database.base import Base, make_engine  # noqa: E402
from database import models  # noqa: E402,F401  (imports register the tables)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The database URL always comes from the app config, never alembic.ini.
config.set_main_option("sqlalchemy.url", load_config().storage.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-friendly ALTERs
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # make_engine also creates the SQLite parent directory if needed.
    connectable = make_engine(config.get_main_option("sqlalchemy.url"))
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
