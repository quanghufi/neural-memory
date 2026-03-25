"""
Auto-import: Run all split SQL files against Supabase via asyncpg.
Each file is small (~300 rows) so individual execution is fast.
"""
import asyncio
import asyncpg
from pathlib import Path

PG_DSN = (
    "postgresql://postgres.ndnzdahhvolftrclunlc:"
    "aQ%40%40020319%40%40@"
    "aws-1-ap-southeast-1.pooler.supabase.com:5432/"
    "postgres"
)

SPLIT_DIR = Path(__file__).parent / "export" / "split"

# Import order: brains first (no FK deps), then neurons, fibers, synapses, etc.
ORDER = ['01_brains', 'neurons', 'fibers', 'synapses', 'fiber_neurons', 'typed_memories']


async def main():
    print("=== Auto-Import to Supabase ===")
    
    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=2, ssl='require')
    
    # Get all SQL files in order
    all_files = sorted(SPLIT_DIR.glob("*.sql"))
    
    # Sort by our preferred order
    def sort_key(f):
        name = f.stem
        for i, prefix in enumerate(ORDER):
            if name.startswith(prefix):
                return (i, name)
        return (99, name)
    
    all_files.sort(key=sort_key)
    
    # First, clear tables (in reverse FK order)
    async with pool.acquire() as conn:
        print("Clearing existing data...")
        await conn.execute("SET session_replication_role = 'replica'")
        for table in reversed(['brains', 'neurons', 'fibers', 'synapses', 'fiber_neurons', 'typed_memories', 'knowledge_gaps']):
            try:
                n = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"')
                if n > 0:
                    await conn.execute(f'DELETE FROM "{table}"')
                    print(f"  Cleared {table} ({n} rows)")
            except:
                pass
        await conn.execute("SET session_replication_role = 'origin'")
    
    # Import each file
    total_ok = 0
    total_err = 0
    
    for i, sql_file in enumerate(all_files):
        sql = sql_file.read_text(encoding='utf-8')
        kb = sql_file.stat().st_size / 1024
        
        try:
            async with pool.acquire() as conn:
                await conn.execute(sql)
            total_ok += 1
            print(f"  [{i+1}/{len(all_files)}] {sql_file.name} ({kb:.0f} KB) OK")
        except Exception as e:
            total_err += 1
            err_msg = str(e)[:100]
            print(f"  [{i+1}/{len(all_files)}] {sql_file.name} ERR: {err_msg}")
    
    # Verify
    async with pool.acquire() as conn:
        print(f"\n=== Verification ===")
        for table in ['brains', 'neurons', 'fibers', 'synapses', 'fiber_neurons', 'typed_memories']:
            try:
                n = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"')
                print(f"  {table}: {n} rows")
            except:
                pass
    
    await pool.close()
    print(f"\nDone: {total_ok} OK, {total_err} errors")


asyncio.run(main())
