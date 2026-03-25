"""
Save SupaBrain context directly to the active brain.
"""
import asyncio
import os
import sys

# Add current dir to path to find supabrain_plugin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from neural_memory.core.brain import Brain
# Force load our plugin
import supabrain_mcp

async def save_context():
    print("Connecting to SupaBrain...")
    brain = await Brain.create()
    
    context = """
# SupaBrain Architecture & Setup
Project: Migrating Neural Memory to Supabase PostgreSQL (Free Tier)

## Architecture
We used a fork-and-adapt approach to bypass the Pro-only limitation:
1. `PostgreSQLStorage` exists in the free `neural-memory` package but is locked.
2. `supabrain_plugin.py` registers it via the plugin system to override the default storage factory.
3. `supabrain_mcp.py` acts as a wrapper that loads credentials from environment variables (`DATABASE_URL`, `NM_MODE=postgres`) and imports the plugin before starting the MCP server.

## New Client Setup
To use this brain on a second machine, you do NOT need a local PostgreSQL server.
1. `git clone https://github.com/quanghufi/neural-memory.git`
2. `pip install neural-memory asyncpg`
3. Update `mcp_config.json` command to point to `supabrain_mcp.py`.

## Migration Tools
Created high-performance batch migration tools to move SQLite -> Supabase:
- `export_brain.py`: Exports SQLite to chunks of SQL INSERT statements (schema-aware, filters out missing columns like `graph_density`).
- `split_sql.py`: Splits large SQL files into ~300-row chunks for SQL Editor limits.
- `import_brain.py`: Auto-imports all split SQL chunks to Supabase using `asyncpg` (much faster than row-by-row inserts).

## Anti-Pause
Supabase free tier auto-pauses after 7 days of inactivity. Created a GitHub Actions cron job (`keep-alive.yml`) that runs every 3 days to briefly connect and prevent pausing. Requires `DATABASE_URL` GitHub Secret.
    """
    
    print("Saving context to Neural Memory...")
    # Save as eternal context
    neuron = await brain.remember(
        content=context,
        type="context",
        tags=["supabrain", "architecture", "setup", "migration", "supabase", "postgresql"],
        priority=10
    )
    
    print(f"Saved successfully! Fiber ID: {neuron.id}")

if __name__ == "__main__":
    asyncio.run(save_context())
