"""
Export v2: Only export columns that exist on BOTH SQLite and Supabase.
Queries Supabase schema first, then generates compatible SQL.
"""
import asyncio
import sqlite3
import asyncpg
from pathlib import Path
from datetime import datetime

DB_PATH = str(Path.home() / ".neuralmemory" / "brains" / "default.db")
PG_DSN = (
    "postgresql://postgres.ndnzdahhvolftrclunlc:"
    "aQ%40%40020319%40%40@"
    "aws-1-ap-southeast-1.pooler.supabase.com:5432/"
    "postgres"
)
OUT_DIR = Path(__file__).parent / "export"

TABLES = [
    "brains", "neurons", "synapses", "fibers",
    "fiber_neurons", "typed_memories", "knowledge_gaps",
]

# Skip these column types (need special handling)
SKIP_PG_TYPES = {'ARRAY', 'USER-DEFINED'}

PG_BOOL_COLS = {
    'is_pinned', 'is_encrypted', 'is_ephemeral', 'synced',
    'has_conflicts', 'encrypted',
}


def escape_sql(val, col_name, pg_type):
    if val is None:
        return 'NULL'
    # Bool conversion
    if col_name in PG_BOOL_COLS or pg_type == 'boolean':
        if isinstance(val, int):
            return 'TRUE' if val else 'FALSE'
        return 'TRUE' if val else 'FALSE'
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, bytes):
        val = val.decode('utf-8', errors='replace')
    val = str(val).replace("'", "''")
    return f"'{val}'"


async def main():
    print("=== Export v2: Schema-aware ===")
    
    local = sqlite3.connect(DB_PATH)
    local.row_factory = sqlite3.Row
    
    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=1, ssl='require')
    OUT_DIR.mkdir(exist_ok=True)
    
    async with pool.acquire() as conn:
        for table in TABLES:
            # Get PG columns
            pg_cols = await conn.fetch(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name=$1 ORDER BY ordinal_position", table)
            pg_map = {r['column_name']: r['data_type'] for r in pg_cols}
            
            if not pg_map:
                print(f"  {table}: not on Supabase, skip")
                continue
            
            # Get SQLite columns
            try:
                rows = local.execute(f"SELECT * FROM {table}").fetchall()
            except:
                print(f"  {table}: not in SQLite, skip")
                continue
            
            if not rows:
                print(f"  {table}: 0 rows")
                continue
            
            sqlite_cols = [d[0] for d in local.execute(f"SELECT * FROM {table} LIMIT 1").description]
            
            # Only columns on BOTH sides, skip ARRAY/USER-DEFINED
            common = []
            for c in sqlite_cols:
                if c in pg_map and pg_map[c] not in SKIP_PG_TYPES:
                    common.append(c)
            
            if not common:
                print(f"  {table}: no compatible columns")
                continue
            
            col_idx = [sqlite_cols.index(c) for c in common]
            col_list = ", ".join(f'"{c}"' for c in common)
            
            # Columns in PG but not SQLite (for info)
            pg_only = [c for c in pg_map if c not in sqlite_cols and pg_map[c] not in SKIP_PG_TYPES]
            sqlite_only = [c for c in sqlite_cols if c not in pg_map]
            if sqlite_only:
                print(f"  {table}: skipping SQLite-only cols: {sqlite_only}")
            
            # Write SQL file
            out_file = OUT_DIR / f"{table}.sql"
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(f"-- {table}: {len(rows)} rows\n")
                f.write(f"-- Columns: {', '.join(common)}\n")
                f.write(f"SET session_replication_role = 'replica';\n")
                f.write(f"DELETE FROM \"{table}\";\n\n")
                
                batch = 100
                for i in range(0, len(rows), batch):
                    chunk = rows[i:i+batch]
                    f.write(f"INSERT INTO \"{table}\" ({col_list}) VALUES\n")
                    
                    val_rows = []
                    for row in chunk:
                        vals = []
                        for j, idx in enumerate(col_idx):
                            vals.append(escape_sql(row[idx], common[j], pg_map[common[j]]))
                        val_rows.append(f"  ({', '.join(vals)})")
                    
                    f.write(",\n".join(val_rows))
                    f.write("\nON CONFLICT DO NOTHING;\n\n")
                
                f.write(f"SET session_replication_role = 'origin';\n")
            
            size_kb = out_file.stat().st_size / 1024
            print(f"  {table}: {len(rows)} rows -> {out_file.name} ({size_kb:.0f} KB)")
    
    local.close()
    await pool.close()
    
    print(f"\nFiles at: {OUT_DIR}")
    print(f"Import order: brains -> neurons -> fibers -> synapses -> fiber_neurons -> typed_memories")


asyncio.run(main())
