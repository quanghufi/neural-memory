# Neural Memory Hub (Self-Hosted)

Deploy Neural Memory Hub on Docker (including MikroTik CHR containers).

## Quick Setup

### 1. Deploy Server
```bash
docker run -d \
  --name nmem-hub \
  -p 8000:8000 \
  -v nmem-data:/root/.neuralmemory \
  ghcr.io/quanghufi/neural-memory:latest
```

### 2. Setup on Client Machines

```bash
# Install neural-memory
pip install neural-memory

# Apply sync URL patch (required for self-hosted servers)
python patch_sync.py

# Configure sync
nmem config set sync.enabled true
nmem config set sync.hub_url "https://your-server-domain.com"
nmem config set sync.auto_sync true
```

Or manually edit `~/.neuralmemory/config.toml`:
```toml
[sync]
enabled = true
hub_url = "https://your-server-domain.com"
auto_sync = true
sync_interval_seconds = 300
conflict_strategy = "prefer_recent"
```

### 3. Sync Data

```bash
# First time: seed change log from existing data
nmem_sync(action='seed')

# Push local → remote
nmem_sync(action='push')

# Pull remote → local
nmem_sync(action='pull')

# Bidirectional sync
nmem_sync(action='full')
```

## Architecture

```
Machine A (MCP) → Local SQLite → nmem_sync(push) → Remote Server
                                                         ↕
Machine B (MCP) → Local SQLite → nmem_sync(pull) ← Remote Server
```

- Each machine keeps a **local SQLite** database (fast, reliable)
- Sync protocol pushes/pulls changes via `/hub/sync` endpoint
- Conflicts resolved by `conflict_strategy` (default: `prefer_recent`)
- Auto-sync every 300 seconds when enabled

## Server API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/hub/sync` | POST | Sync protocol |
| `/hub/register` | POST | Register device |
| `/hub/status/{brain_id}` | GET | Brain sync status |
| `/memory/encode` | POST | Store a memory |
| `/memory/query` | POST | Query memories |
| `/memory/neurons` | GET/POST | CRUD neurons |
| `/memory/synapses` | GET/POST | CRUD synapses |
| `/ui` | GET | Dashboard UI |

## Why `patch_sync.py`?

The default `neural-memory` package adds a `/v1` prefix to sync URLs for non-localhost servers (designed for Cloudflare Workers cloud hub). Self-hosted `nmem serve` exposes routes without this prefix. The patch removes the `/v1` prefix so sync works with self-hosted servers.

## Files

- `Dockerfile` — Docker image for neural-memory server
- `patch_sync.py` — Client-side fix for sync URL
- `.github/workflows/build.yml` — Auto-build Docker image
