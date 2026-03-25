# SupaBrain — Neural Memory on Supabase

Chạy neural-memory brain trên **Supabase PostgreSQL** (free tier). Đồng bộ multi-device, không cần bản Pro.

## Kiến trúc

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ MCP Client  │────▶│ neural-memory    │────▶│  Supabase    │
│ (Gemini/    │     │ PostgreSQLStorage│     │  PostgreSQL  │
│  Claude)    │     │ + supabrain_plugin│    │  (free tier) │
└─────────────┘     └──────────────────┘     └──────────────┘
       ↑                                            ↑
   Máy bất kỳ                              Cloud (Singapore)
```

---

## 🚀 Triển khai máy MỚI (5 phút)

### Bước 1: Clone repo
```bash
git clone https://github.com/quanghufi/neural-memory.git
cd neural-memory
```

### Bước 2: Cài dependencies
```bash
pip install neural-memory asyncpg
```

### Bước 3: Config MCP server

Thêm vào file MCP config của editor (VS Code / Gemini / Claude):

**File config:** 
- VS Code Gemini: `~/.gemini/antigravity/mcp_config.json`
- Claude Code: `~/.claude/mcp_config.json`

```json
{
  "mcpServers": {
    "neural-memory": {
      "type": "stdio",
      "command": "python",
      "args": [
        "/absolute/path/to/neural-memory/supabrain_mcp.py"
      ]
    }
  }
}
```

> ⚠️ **Sửa path** cho đúng vị trí clone trên máy.

### Bước 4: Restart editor

Reload/restart VS Code hoặc Claude. MCP server sẽ tự kết nối Supabase.

### Bước 5: Verify

Trong chat, thử:
- `nmem_recall("test")` — recall memories
- `nmem_remember("hello from machine 2")` — lưu memory mới

**Xong!** Cả 2 máy giờ dùng chung 1 brain trên Supabase.

---

## 🛠️ Setup Supabase từ đầu (lần đầu tiên)

Nếu chưa có Supabase project:

### 1. Tạo project
- Vào [supabase.com](https://supabase.com) → New Project
- Region: **Singapore** (gần VN nhất)
- Nhớ password database

### 2. Deploy schema
```bash
# Sửa credentials trong .env
cp .env.example .env
# Edit .env với DATABASE_URL của bạn

# Chạy setup
python setup_supabrain.py
```

### 3. Cập nhật credentials trong `supabrain_mcp.py`

Sửa dòng `DATABASE_URL` trong file `supabrain_mcp.py` với connection string của bạn:
```
postgresql://postgres.YOUR_REF:YOUR_PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
```

> Password có ký tự đặc biệt (`@`, `#`) phải URL-encode (`@` → `%40`)

### 4. Test
```bash
python test_e2e.py
```

---

## 📁 Cấu trúc dự án

```
nmem-hub-chr/
├── supabrain_mcp.py        # Entry point — MCP server wrapper
├── supabrain_plugin.py     # Đăng ký PostgreSQLStorage (bypass Pro)
├── setup_supabrain.py      # Deploy schema lên Supabase
├── export_brain.py         # Export SQLite → SQL files
├── import_brain.py         # Import SQL files → Supabase
├── test_e2e.py             # Test encode + recall
├── patch_sync.py           # Patch sync endpoint (nếu cần)
│
├── scripts/
│   ├── deploy_schema.sql   # Schema SQL (11 tables)
│   ├── rls_policies.sql    # Row Level Security policies
│   ├── migrate_brain.py    # Migration helper
│   ├── split_sql.py        # Tách file SQL lớn
│   └── save_context.py     # Save context helper
│
└── docs/
    ├── BRIEF.md            # Project brief
    ├── factory_ref.py      # Factory reference
    └── pg_schema_ref.py    # PostgreSQL schema reference
```

---

## 📦 Migrate brain local → Supabase

Nếu đã có brain trên SQLite local và muốn chuyển lên cloud:

```bash
# 1. Export ra SQL files
python export_brain.py

# 2. Tách file nhỏ
python scripts/split_sql.py

# 3. Import lên Supabase (tự động)
python import_brain.py
```

---

## ⚠️ Supabase Free Tier

| Giới hạn | Mức | Ghi chú |
|----------|-----|---------|
| Storage | 500 MB | ~100K+ memories |
| Bandwidth | 5 GB/month | Đủ cho text |
| Auto-pause | 7 ngày | → GitHub Actions keep-alive |

### Anti-pause
GitHub Actions cron ping mỗi 3 ngày. Setup:
1. Push repo lên GitHub
2. **Settings → Secrets → Actions** → thêm `DATABASE_URL`
3. Tự chạy (hoặc manual: Actions → Keep Supabase Alive → Run)

---

## License
MIT
