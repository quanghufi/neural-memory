"""
Split large SQL export files into chunks small enough for Supabase SQL Editor.
Max ~500 rows per file to stay well under the size limit.
"""
import os
from pathlib import Path

EXPORT_DIR = Path(__file__).parent / "export"
SPLIT_DIR = EXPORT_DIR / "split"
SPLIT_DIR.mkdir(exist_ok=True)

MAX_ROWS_PER_FILE = 300  # ~300 rows per chunk = ~200KB

def split_sql(filename):
    """Split a SQL file into chunks."""
    filepath = EXPORT_DIR / filename
    if not filepath.exists():
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract table name from first INSERT
    lines = content.split('\n')
    table_name = filename.replace('.sql', '')
    
    # Find all INSERT blocks
    # Each block starts with INSERT INTO and ends with ON CONFLICT DO NOTHING;
    blocks = []
    current_block = []
    in_insert = False
    
    for line in lines:
        if line.startswith('INSERT INTO'):
            in_insert = True
            current_block = [line]
        elif in_insert:
            current_block.append(line)
            if 'ON CONFLICT DO NOTHING;' in line:
                blocks.append('\n'.join(current_block))
                current_block = []
                in_insert = False
    
    if not blocks:
        print(f"  {filename}: no INSERT blocks found")
        return
    
    # Count total value rows
    total_values = 0
    for block in blocks:
        total_values += block.count('  (')
    
    if total_values <= MAX_ROWS_PER_FILE:
        # Small enough, just copy
        print(f"  {filename}: {total_values} rows, no split needed")
        return
    
    # Rebuild as chunked files
    # Each original block has ~100 rows. Group blocks to stay under limit.
    chunk_idx = 1
    current_chunks = []
    current_rows = 0
    
    for block in blocks:
        block_rows = block.count('  (')
        
        if current_rows + block_rows > MAX_ROWS_PER_FILE and current_chunks:
            # Write current chunk
            write_chunk(table_name, chunk_idx, current_chunks)
            chunk_idx += 1
            current_chunks = []
            current_rows = 0
        
        current_chunks.append(block)
        current_rows += block_rows
    
    # Write last chunk
    if current_chunks:
        write_chunk(table_name, chunk_idx, current_chunks)
        chunk_idx += 1
    
    total_files = chunk_idx - 1
    print(f"  {filename}: {total_values} rows -> {total_files} files")


def write_chunk(table_name, idx, blocks):
    """Write a chunk of INSERT blocks to a file."""
    out_file = SPLIT_DIR / f"{table_name}_{idx:02d}.sql"
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f"-- {table_name} chunk {idx}\n")
        f.write(f"SET session_replication_role = 'replica';\n\n")
        for block in blocks:
            f.write(block)
            f.write('\n\n')
        f.write(f"SET session_replication_role = 'origin';\n")


def main():
    print("=== Splitting SQL files ===")
    
    # brains.sql is tiny, just copy with DELETE
    brains_src = EXPORT_DIR / "brains.sql"
    if brains_src.exists():
        import shutil
        shutil.copy(brains_src, SPLIT_DIR / "01_brains.sql")
        print(f"  brains.sql: copied as 01_brains.sql")
    
    # Split large files
    for f in ['neurons.sql', 'fibers.sql', 'synapses.sql', 'fiber_neurons.sql', 'typed_memories.sql']:
        split_sql(f)
    
    # List all split files
    print(f"\n=== Split files ===")
    files = sorted(SPLIT_DIR.glob("*.sql"))
    for f in files:
        kb = f.stat().st_size / 1024
        print(f"  {f.name} ({kb:.0f} KB)")
    
    print(f"\nTotal: {len(files)} files in {SPLIT_DIR}")
    print(f"Import order: 01_brains -> neurons_* -> fibers_* -> synapses_* -> fiber_neurons_* -> typed_memories_*")


if __name__ == "__main__":
    main()
