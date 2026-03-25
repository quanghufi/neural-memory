"""
SupaBrain Plugin — Register PostgreSQLStorage for Supabase.

This script patches neural-memory to use PostgreSQLStorage
pointing at your Supabase PostgreSQL instance.

Usage:
    1. Set DATABASE_URL in .env or environment
    2. Run: python setup_supabrain.py
    3. Or import this in your MCP server startup
"""

import asyncio
import os
import sys
from pathlib import Path


async def setup_supabrain():
    """Initialize PostgreSQLStorage with Supabase credentials and run schema."""
    # Load .env if exists
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set! Copy .env.example to .env and fill in credentials.")
        sys.exit(1)

    # Parse DATABASE_URL
    # Format: postgresql://user:pass@host:port/dbname?sslmode=require
    from urllib.parse import urlparse
    parsed = urlparse(database_url)

    host = parsed.hostname
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    password = parsed.password or ""
    database = parsed.path.lstrip("/") or "postgres"
    ssl = "sslmode=require" in database_url

    print(f"🔌 Connecting to Supabase PostgreSQL: {host}:{port}/{database}")

    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg not installed. Run: pip install asyncpg")
        sys.exit(1)

    # Connect and verify
    try:
        ssl_ctx = "require" if ssl else None
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            ssl=ssl_ctx,
        )
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Connected! PostgreSQL {version[:60]}...")

        # Check pgvector
        ext = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        if ext:
            print("✅ pgvector extension is enabled")
        else:
            print("⚠️  pgvector not enabled. Enabling now...")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            print("✅ pgvector enabled!")

        # Run schema
        print("\n📦 Deploying neural-memory schema...")
        schema_file = Path(__file__).parent / "scripts" / "deploy_schema.sql"
        if schema_file.exists():
            sql = schema_file.read_text(encoding="utf-8")
            # Split by semicolons and execute each statement
            statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
            for stmt in statements:
                if stmt:
                    try:
                        await conn.execute(stmt)
                    except asyncpg.exceptions.DuplicateObjectError:
                        pass  # Already exists
                    except asyncpg.exceptions.DuplicateTableError:
                        pass  # Already exists
            print("✅ Schema deployed! (11 tables + indexes)")
        else:
            print(f"⚠️  Schema file not found: {schema_file}")
            print("   Run from project root directory or check scripts/deploy_schema.sql exists")

        # Verify tables
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        print(f"\n📋 Tables in database ({len(tables)}):")
        for t in tables:
            print(f"   • {t['table_name']}")

        await conn.close()
        print("\n🎉 SupaBrain setup complete!")
        print("\n📌 Next steps:")
        print("   1. Set NM_MODE=postgres in your MCP server config")
        print("   2. Set DATABASE_URL in your MCP server env")
        print("   3. Restart MCP server")
        print("   4. Test: nmem_remember + nmem_recall")

    except asyncpg.exceptions.InvalidPasswordError:
        print("❌ Invalid password! Check DATABASE_URL in .env")
        sys.exit(1)
    except OSError as e:
        print(f"❌ Connection failed: {e}")
        print("   Check if Supabase project is active (not paused)")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(setup_supabrain())
