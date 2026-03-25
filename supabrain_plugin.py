"""
SupaBrain Plugin — Register PostgreSQLStorage for Supabase with neural-memory.

This plugin makes neural-memory use Supabase PostgreSQL instead of local SQLite.
It registers PostgreSQLStorage as the Pro storage class via neural-memory's
plugin system.

Usage:
    import supabrain_plugin  # before starting MCP server

Or set as env var in MCP config:
    NM_SUPABRAIN_PLUGIN=1
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


def _get_supabase_storage_class():
    """Create a wrapper class that connects PostgreSQLStorage to Supabase."""
    from neural_memory.storage.postgres import PostgreSQLStorage
    from neural_memory.storage.postgres.postgres_schema import ensure_schema

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set, cannot use Supabase storage")
        return None

    parsed = urlparse(database_url)
    ssl_mode = parse_qs(parsed.query).get("sslmode", [""])[0] or None

    class SupabrainStorage(PostgreSQLStorage):
        """PostgreSQLStorage pre-configured for Supabase."""

        def __init__(self, base_dir=None, brain_id=None, **kwargs):
            super().__init__(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                user=parsed.username or "postgres",
                password=parsed.password or "",
                database=parsed.path.lstrip("/") or "postgres",
                embedding_dim=kwargs.get("embedding_dim", 384),
            )
            self._ssl = "require" if ssl_mode == "require" else None
            if brain_id:
                self.set_brain(brain_id)

        async def initialize(self) -> None:
            """Create connection pool and schema using Supabase SSL settings."""
            import asyncpg

            self._pool = await asyncpg.create_pool(
                host=self._host,
                port=self._port,
                database=self._database,
                user=self._user,
                password=self._password or None,
                min_size=1,
                max_size=10,
                command_timeout=60,
                ssl=self._ssl,
            )
            await ensure_schema(self._pool, embedding_dim=self._embedding_dim)

        async def open(self) -> None:
            """Called by the storage factory."""
            await self.initialize()

    return SupabrainStorage


def register_supabrain() -> bool:
    """Register SupaBrain as a neural-memory Pro plugin."""
    try:
        from neural_memory.plugins import register
        from neural_memory.plugins.base import ProPlugin

        storage_cls = _get_supabase_storage_class()
        if storage_cls is None:
            return False

        class SupabrainPlugin(ProPlugin):
            def __init__(self, storage_class: type) -> None:
                self._storage_cls = storage_class

            @property
            def name(self) -> str:
                return "supabrain"

            @property
            def version(self) -> str:
                return "1.1.0"

            def get_retrieval_strategies(self) -> dict[str, Callable[..., Any]]:
                return {}

            def get_compression_fn(self) -> Callable[..., Any] | None:
                return None

            def get_consolidation_strategies(self) -> dict[str, Callable[..., Any]]:
                return {}

            def get_storage_class(self) -> type | None:
                return self._storage_cls

        register(SupabrainPlugin(storage_cls))
        logger.info("SupaBrain plugin registered using Supabase PostgreSQL")
        return True
    except Exception:
        logger.exception("Failed to register SupaBrain plugin")
        return False


# Auto-register on import
if os.environ.get("DATABASE_URL"):
    register_supabrain()
