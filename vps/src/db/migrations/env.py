"""
Alembic environment configuration for async migrations.

Configures Alembic to use the async SQLAlchemy engine and imports
the Base metadata for autogenerate support. Reads DATABASE_URL from
the environment (same source as vps/src/db/session.py).

CHANGELOG:
- 2026-02-14: Initial creation (STORY-008)

TODO:
- None
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.db.models import Base

# Alembic Config object for access to .ini values.
config = context.config

# Set up Python logging from the config file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy MetaData for autogenerate support.
target_metadata = Base.metadata


def get_url() -> str:
    """Get the database URL from environment variables.

    Returns:
        str: The DATABASE_URL from the environment.

    Raises:
        RuntimeError: If DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations with a given connection.

    Args:
        connection: A synchronous database connection.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine.

    Creates an async engine and runs migrations within a connection.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Delegates to async runner for asyncpg compatibility.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
