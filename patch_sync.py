"""Patch neural-memory sync_handler.py to fix /v1 prefix bug.

The default sync_handler.py adds /v1 prefix to URLs for non-localhost servers,
but self-hosted nmem serve exposes routes at /hub/sync directly (no /v1).

Run this script after `pip install neural-memory` to fix the sync URL:
    python patch_sync.py
"""

import importlib
import re
import sys
from pathlib import Path


def find_sync_handler() -> Path | None:
    """Find sync_handler.py in the installed neural_memory package."""
    try:
        import neural_memory
        pkg_dir = Path(neural_memory.__file__).parent
        handler = pkg_dir / "mcp" / "sync_handler.py"
        if handler.exists():
            return handler
    except ImportError:
        pass

    # Fallback: search common paths
    for site_dir in sys.path:
        candidate = Path(site_dir) / "neural_memory" / "mcp" / "sync_handler.py"
        if candidate.exists():
            return candidate

    return None


def patch_file(filepath: Path) -> bool:
    """Patch _build_sync_url and _build_hub_url to remove /v1 prefix."""
    content = filepath.read_text(encoding="utf-8")

    # Check if already patched
    if 'return f"{base}/v1/hub/sync"' not in content and 'return f"{base}/v1{path}"' not in content:
        print(f"[OK] Already patched: {filepath}")
        return True

    # Patch _build_sync_url: remove /v1 prefix logic
    old_sync = '''def _build_sync_url(hub_url: str) -> str:
    """Build the sync endpoint URL with version prefix.

    Cloud hub uses /v1/hub/sync, local hub uses /hub/sync.
    """
    base = hub_url.rstrip("/")
    if "localhost" in base or "127.0.0.1" in base:
        return f"{base}/hub/sync"
    return f"{base}/v1/hub/sync"'''

    new_sync = '''def _build_sync_url(hub_url: str) -> str:
    """Build the sync endpoint URL.

    Uses /hub/sync for all servers (self-hosted nmem serve and cloud hubs
    both expose this path directly).
    """
    base = hub_url.rstrip("/")
    return f"{base}/hub/sync"'''

    # Patch _build_hub_url: remove /v1 prefix logic
    old_hub = '''def _build_hub_url(hub_url: str, path: str) -> str:
    """Build a hub endpoint URL with version prefix."""
    base = hub_url.rstrip("/")
    if "localhost" in base or "127.0.0.1" in base:
        return f"{base}{path}"
    return f"{base}/v1{path}"'''

    new_hub = '''def _build_hub_url(hub_url: str, path: str) -> str:
    """Build a hub endpoint URL."""
    base = hub_url.rstrip("/")
    return f"{base}{path}"'''

    patched = content.replace(old_sync, new_sync).replace(old_hub, new_hub)

    if patched == content:
        # Try regex fallback for slightly different formatting
        patched = re.sub(
            r'return f"{base}/v1/hub/sync"',
            'return f"{base}/hub/sync"',
            content,
        )
        patched = re.sub(
            r'return f"{base}/v1{path}"',
            'return f"{base}{path}"',
            patched,
        )

    if patched == content:
        print(f"[WARN] Could not patch (format mismatch): {filepath}")
        return False

    filepath.write_text(patched, encoding="utf-8")
    print(f"[PATCHED] {filepath}")
    return True


def main():
    print("Neural Memory Sync URL Patch")
    print("=" * 40)

    handler = find_sync_handler()
    if handler is None:
        print("[ERROR] Could not find sync_handler.py")
        print("Make sure neural-memory is installed: pip install neural-memory")
        sys.exit(1)

    print(f"Found: {handler}")
    success = patch_file(handler)
    if success:
        print("\nDone! Restart your MCP server for changes to take effect.")
    else:
        print("\nPatch failed. You may need to edit the file manually.")
        sys.exit(1)


if __name__ == "__main__":
    main()
