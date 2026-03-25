"""
SupaBrain Plugin — Register PostgreSQLStorage for Supabase with neural-memory.

This plugin makes neural-memory use Supabase PostgreSQL instead of local SQLite.
It registers PostgreSQLStorage as the Pro storage class via neural-memory's plugin system.

Usage:
    import supabrain_plugin  # before starting MCP server
    
Or set as env var in MCP config:
    NM_SUPABRAIN_PLUGIN=1
"""

import os
import logging

logger = logging.getLogger(__name__)


def _get_supabase_storage_class():
    """Create a wrapper class that connects PostgreSQLStorage to Supabase."""
    from neural_memory.storage.postgres import PostgreSQLStorage

    # Parse connection from env
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set, cannot use Supabase storage")
        return None

    from urllib.parse import urlparse
    parsed = urlparse(database_url)

    class SupabrainStorage(PostgreSQLStorage):
        """PostgreSQLStorage pre-configured for Supabase."""

        def __init__(self, base_dir=None, brain_id=None, **kwargs):
            super().__init__(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                user=parsed.username or "postgres",
                password=parsed.password or "",
                database=parsed.path.lstrip("/") or "postgres",
            )
            if brain_id:
                self.set_brain(brain_id)

        async def open(self):
            """Called by the factory — initialize the connection pool."""
            await self.initialize()

    return SupabrainStorage


def register_supabrain():
    """Register SupaBrain as a neural-memory Pro plugin."""
    try:
        from neural_memory.plugins import register

        storage_cls = _get_supabase_storage_class()
        if storage_cls is None:
            return False

        class SupabrainPlugin:
            name = "supabrain"
            version = "1.0.0"
            _storage_cls = storage_cls

            @staticmethod
            def get_storage_class():
                return SupabrainPlugin._storage_cls

        register(SupabrainPlugin)
        logger.info("✅ SupaBrain plugin registered — using Supabase PostgreSQL")
        return True
    except Exception as e:
        logger.error(f"Failed to register SupaBrain plugin: {e}")
        return False


# Auto-register on import
if os.environ.get("DATABASE_URL"):
    register_supabrain()
