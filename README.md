# SupaBrain — Neural Memory on Supabase

Neural Memory brain storage on **Supabase free tier** PostgreSQL. No code fork needed — uses neural-memory's built-in `PostgreSQLStorage` backend.

## Quick Start

### 1. Setup Supabase
- Create project at [supabase.com](https://supabase.com) (Region: Singapore)
- Enable `pgvector` extension (SQL Editor → `CREATE EXTENSION vector`)

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

### 3. Deploy Schema
```bash
pip install asyncpg
python setup_supabrain.py
```

### 4. Test
```bash
python test_e2e.py
```

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ MCP Client  │────▶│ neural-memory    │────▶│  Supabase    │
│ (Claude/    │     │ PostgreSQLStorage│     │  PostgreSQL  │
│  Gemini)    │     │ + asyncpg        │     │  + pgvector  │
└─────────────┘     └──────────────────┘     └──────────────┘
```

- **11 tables**: brains, neurons, synapses, fibers, typed_memories, etc.
- **pgvector**: 384-dim embedding search
- **tsvector**: Full-text search
- **Session Pooler**: IPv4 compatible connection

## Files

| File | Purpose |
|------|---------|
| `scripts/deploy_schema.sql` | Full PostgreSQL schema |
| `scripts/rls_policies.sql` | Row Level Security (optional) |
| `.env.example` | Connection template |
| `setup_supabrain.py` | One-click setup |
| `supabrain_plugin.py` | neural-memory Pro plugin adapter |
| `test_e2e.py` | End-to-end test |

## Supabase Free Tier Limits

| Resource | Limit | Usage |
|----------|-------|-------|
| Storage | 500 MB | ~100K+ memories |
| Bandwidth | 5 GB/month | Sufficient for text |
| Auto-pause | 7 days inactivity | → `.github/workflows/keep-alive.yml` |

## Anti-Pause

GitHub Actions cron pings Supabase every 3 days. Setup:
1. Push this repo to GitHub
2. Add `DATABASE_URL` to repo **Settings → Secrets → Actions**
3. The workflow runs automatically

## Connection

Uses **Session Pooler** (IPv4 compatible):
```
postgresql://postgres.PROJECT_REF:PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
```

## License

MIT
