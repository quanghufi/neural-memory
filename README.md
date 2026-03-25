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
pip install -r requirements.txt
```

### Bước 3: Tạo `.env`

```bash
cp .env.example .env
```

Mở `.env` và điền `YOUR_DATABASE_PASSWORD`.

Mặc định nên dùng **session pooler**:

```env
DATABASE_URL=postgresql://postgres.YOUR_REF:YOUR_DATABASE_PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require
```

Ví dụ với project ref `ndnzdahhvolftrclunlc`:

```env
DATABASE_URL=postgresql://postgres.ndnzdahhvolftrclunlc:YOUR_DATABASE_PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require
```

Nếu password có ký tự đặc biệt như `@`, `#`, `%`, phải URL-encode trước khi điền vào `DATABASE_URL`.

### Bước 4: Config MCP server

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
> Nếu editor vẫn trỏ vào `nmem-mcp` hoặc `python -m neural_memory.mcp`, nó sẽ tiếp tục dùng local brain ở `~/.neuralmemory/` thay vì Supabase.

### Bước 5: Restart editor

Reload/restart VS Code hoặc Claude. MCP server sẽ tự kết nối Supabase.

Rất quan trọng: phải restart hẳn MCP process cũ. Nếu editor giữ process `neural-memory` cũ từ trước khi sửa config, nó có thể vẫn bám local SQLite cache.

Khi `supabrain_mcp.py` khởi động, nó sẽ tự cập nhật file:

```text
~/.neuralmemory/config.toml
```

Các dòng quan trọng phải có ở **top-level**:

```toml
current_brain = "default"
storage_backend = "postgres"
```

Và phải có section:

```toml
[postgres]
host = "aws-1-ap-southeast-1.pooler.supabase.com"
port = 5432
database = "postgres"
user = "postgres.YOUR_REF"
password = ""
```

Lưu ý: `storage_backend = "postgres"` phải nằm ở top-level, không được nằm bên trong `[sync]` hay section nào khác. Nếu nằm sai chỗ, `neural-memory` sẽ âm thầm fallback về SQLite local.

### Bước 6: Verify

Trong chat, thử:
- `nmem_recall("test")` — recall memories
- `nmem_remember("hello from machine 2")` — lưu memory mới
- `nmem_stats()` — kiểm tra brain hiện tại có dữ liệu thật không

**Xong!** Cả 2 máy giờ dùng chung 1 brain trên Supabase.

Nếu `nmem_stats()` vẫn ra kiểu:
- `brain: "default"`
- `neuron_count: 0`
- `fiber_count: 0`
- `db_size_bytes` giống SQLite local

thì gần như chắc chắn editor đang chạy MCP process cũ hoặc đang trỏ nhầm sang `nmem-mcp` mặc định thay vì `supabrain_mcp.py`.

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

### 3. Cập nhật credentials trong `.env`

Sửa `DATABASE_URL` trong file `.env` với connection string của bạn:
```
postgresql://postgres.YOUR_REF:YOUR_PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
```

> Password có ký tự đặc biệt (`@`, `#`) phải URL-encode (`@` → `%40`)

`supabrain_mcp.py` sẽ tự đọc `.env`, set `DATABASE_URL`, rồi ghi `storage_backend = "postgres"` vào `~/.neuralmemory/config.toml`. Không cần hardcode password trong source nữa.

### 4. Restart MCP process

Sau khi đổi `.env`, hãy restart editor hoặc remove/add lại MCP server để process cũ bị hạ hoàn toàn.

### 5. Kiểm tra `config.toml` nếu cần

Thông thường không cần sửa tay file này, vì `supabrain_mcp.py` sẽ tự ghi đúng.

Chỉ kiểm tra tay khi:
- `test_e2e.py` kết nối được Postgres nhưng editor vẫn thấy brain rỗng
- `nmem_stats()` vẫn giống local SQLite
- bạn nghi editor đang dùng config cũ

File nằm ở:

```text
~/.neuralmemory/config.toml
```

Checklist:
- có `storage_backend = "postgres"` ở top-level
- có section `[postgres]`
- `host`, `port`, `database`, `user` đúng với Supabase project

### 6. Test kết nối thật

```bash
python test_e2e.py
```

Nếu chạy thành công, bạn sẽ thấy:
- `Existing brains: ...`
- `Memory encoded!`
- `Recall: ...`
- `All tests done!`

Nếu bị `InvalidPasswordError` thì password trong `.env` chưa đúng.
Nếu `test_e2e.py` pass nhưng trong editor vẫn ra brain rỗng, nguyên nhân thường là MCP process cũ chưa restart.

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

Sau khi migrate xong, restart editor/MCP để các tool `nmem_*` nạp lại backend Postgres mới.

---

## 🔎 Troubleshooting

### Triệu chứng: `test_e2e.py` pass nhưng editor vẫn chỉ thấy local brain

Nguyên nhân thường gặp:
- MCP config đang trỏ nhầm vào `nmem-mcp` hoặc `python -m neural_memory.mcp`
- Editor chưa restart nên vẫn giữ process cũ
- `storage_backend = "postgres"` chưa được nạp lại trong `~/.neuralmemory/config.toml`

Cách xử lý:
1. Kiểm tra MCP config đang chạy đúng `python /path/to/supabrain_mcp.py`
2. Restart editor hoàn toàn
3. Mở `~/.neuralmemory/config.toml` kiểm tra `storage_backend = "postgres"` có nằm ở top-level không
4. Gọi lại `nmem_stats()`

### Triệu chứng: `InvalidPasswordError`

Nguyên nhân:
- Password database Supabase sai
- Password có ký tự đặc biệt nhưng chưa URL-encode trong `DATABASE_URL`

### Triệu chứng: direct connection không chạy

Nếu Supabase báo direct connection không IPv4 compatible, hãy dùng session pooler:

```env
DATABASE_URL=postgresql://postgres.YOUR_REF:YOUR_DATABASE_PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require
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

## 📦 Dependencies & Upgrade

Version đang dùng được lock trong `requirements.txt`:

```
neural-memory @ git+https://github.com/nhadaututtheky/neural-memory.git@v4.20.0
asyncpg
```

### Cài lần đầu
```bash
pip install -r requirements.txt
```

### Khi muốn update neural-memory lên version mới

1. Kiểm tra [release notes](https://github.com/nhadaututtheky/neural-memory/releases) xem có breaking changes không
2. Đổi version trong `requirements.txt`:
   ```
   neural-memory @ git+https://...@v4.21.0   ← đổi số version
   ```
3. Cài và test:
   ```bash
   pip install -r requirements.txt --upgrade
   python test_e2e.py
   ```
4. Nếu MCP không start → kiểm tra import path trong `supabrain_plugin.py` có còn đúng không

> **Lưu ý:** Data trên Supabase không bị ảnh hưởng khi upgrade. Chỉ có MCP server có thể cần fix nếu internal API thay đổi.

---

## License
MIT
