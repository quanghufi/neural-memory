# CodeIntel for SupaBrain

CodeIntel la lop code intelligence AST-based cho `nmem-hub-chr`.
Nó index symbol graph cua codebase vao Neural Memory PostgreSQL brain va expose qua MCP tools de tim symbol, callers, callees, va impact.

## Scope v1

CodeIntel v1 hien ho tro:

- Python
- JavaScript
- TypeScript

Features da hoan thien trong v1:

- Symbol extraction: `module`, `function`, `method`, `class`, `interface`
- Relations:
  - `CALLS`
  - `IMPORTS`
  - `EXTENDS`
  - `IMPLEMENTS`
  - `CONTAINS`
- Generation lifecycle:
  - `building`
  - `active`
  - `gc`
  - `failed`
- Per-file rollback khi index bi loi
- Structured `unsupported` response cho cac language de danh dau v2

Khong nam trong v1:

- Go / Rust / Java / C / C++ / Ruby / PHP
- Data-flow analysis
- Full semantic resolution ngoai local project imports

## Files Lien Quan

- [supabrain_mcp.py](C:/Users/quangda/Downloads/nmem-hub-chr/supabrain_mcp.py)
- [codeintel/parser.py](C:/Users/quangda/Downloads/nmem-hub-chr/codeintel/parser.py)
- [codeintel/storage.py](C:/Users/quangda/Downloads/nmem-hub-chr/codeintel/storage.py)
- [codeintel/tools.py](C:/Users/quangda/Downloads/nmem-hub-chr/codeintel/tools.py)
- [test_codeintel.py](C:/Users/quangda/Downloads/nmem-hub-chr/test_codeintel.py)
- [anti.md](C:/Users/quangda/Downloads/nmem-hub-chr/anti.md)

## Kien Truc Ngan Gon

```text
Codebase
  -> tree-sitter parser
  -> symbols + edges
  -> CodeIntelStorage
  -> neurons + synapses trong PostgreSQL brain
  -> MCP tools
```

Flow index:

1. Scan project
2. Parse tung file thanh symbol + edges
3. Store symbols theo generation moi
4. Store edges sau khi da co du symbol
5. Verify count
6. Activate generation moi
7. Generation cu thanh `gc`

## Data Model

Moi symbol duoc luu thanh mot neuron `entity` voi metadata:

- `symbol_id`
- `project_path`
- `generation_id`
- `file`
- `line`
- `kind`
- `language`
- `name`
- `qualified_name`
- `signature`
- `tags`

Moi relation duoc luu thanh mot synapse `RELATED_TO` va phan biet bang:

- `metadata.edge_type = "CALLS"`
- `metadata.edge_type = "IMPORTS"`
- `metadata.edge_type = "EXTENDS"`
- `metadata.edge_type = "IMPLEMENTS"`
- `metadata.edge_type = "CONTAINS"`

Moi lan index tao mot generation neuron rieng voi:

- `generation_id`
- `project_path`
- `status`
- `symbol_count`
- `edge_count`
- `skipped_files`

## Prerequisites

- Windows PowerShell
- Python 3.12+
- PostgreSQL VPS da cau hinh qua `DATABASE_URL`
- Dependencies trong [requirements.txt](C:/Users/quangda/Downloads/nmem-hub-chr/requirements.txt)

## Cai Dat

```powershell
cd C:\Users\quangda\Downloads\nmem-hub-chr
python -m pip install -r requirements.txt
```

Dam bao `.env` co it nhat:

```env
NM_MODE=postgres
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@YOUR_HOST:5432/neural_memory
```

## Chay MCP Server

Nen dung mot brain rieng cho CodeIntel de de quan ly:

```powershell
$env:NEURALMEMORY_BRAIN="nmem_hub_chr_codeintel"
python supabrain_mcp.py
```

Neu ban dang dung editor/MCP client, config phai tro vao:

```text
python C:\Users\quangda\Downloads\nmem-hub-chr\supabrain_mcp.py
```

Khong tro nham vao `nmem-mcp` mac dinh, neu khong se bo qua wrapper va plugin CodeIntel.

## MCP Tools

CodeIntel register 5 tools:

- `nmem_codeintel_index`
- `nmem_codeintel_search`
- `nmem_codeintel_callers`
- `nmem_codeintel_callees`
- `nmem_codeintel_impact`

### 1. Index Codebase

```json
{
  "path": "C:\\Users\\quangda\\Downloads\\nmem-hub-chr",
  "force": true
}
```

Field:

- `path`: absolute path toi repo
- `force`: xoa index CodeIntel cu cua dung `project_path` roi build lai
- `max_files`: optional, mac dinh `5000`
- `extensions`: optional allow-list

Ket qua thanh cong:

```json
{
  "status": "success",
  "generation_id": "fa3b868613194b0e",
  "files_scanned": 2,
  "symbols": 4,
  "edges": 4,
  "skipped": 0,
  "time": 0.703
}
```

Ket qua unsupported:

```json
{
  "status": "unsupported",
  "files_scanned": 0,
  "planned_files": ["main.go"],
  "planned_languages": ["go"],
  "message": "Only planned-v2 languages were found for this path"
}
```

### 2. Search Symbol

```json
{
  "query": "run",
  "project_path": "C:\\Users\\quangda\\Downloads\\nmem-hub-chr",
  "kind": "function",
  "limit": 20
}
```

Dung `search` de lay `symbol_id` truoc khi goi graph tools.

### 3. Tim Callers

```json
{
  "symbol_id": "SYMBOL_ID",
  "project_path": "C:\\Users\\quangda\\Downloads\\nmem-hub-chr",
  "limit": 20
}
```

### 4. Tim Callees

```json
{
  "symbol_id": "SYMBOL_ID",
  "project_path": "C:\\Users\\quangda\\Downloads\\nmem-hub-chr",
  "limit": 20
}
```

### 5. Tinh Impact

```json
{
  "symbol_id": "SYMBOL_ID",
  "project_path": "C:\\Users\\quangda\\Downloads\\nmem-hub-chr",
  "max_depth": 3,
  "max_results": 100
}
```

Impact hien tai la reverse-call BFS:

- depth mac dinh `3`
- max results mac dinh `100`
- co `visited set`
- tra ve `risk`, `affected_files`, `affected_symbols`, `truncated`

## Quy Trinh Dung Khuyen Nghi

1. Chon 1 brain rieng cho repo.
2. Chay `nmem_codeintel_index`.
3. Chay `nmem_codeintel_search` de lay `symbol_id`.
4. Chay `nmem_codeintel_callers`, `nmem_codeintel_callees`, hoac `nmem_codeintel_impact`.
5. Moi khi codebase doi lon, index lai voi `force: true`.

Vi du:

1. Search `"CodeIntelPlugin"`
2. Lay `symbol_id`
3. Chay `impact`
4. Xem file nao se bi anh huong neu sua symbol do

## Hanh Vi Quan Trong

### Generation Safety

CodeIntel khong expose graph dang build dở.
Chi generation `active` moi duoc query.

Neu index fail:

- generation moi se thanh `failed`
- generation dang `active` truoc do van duoc giu

### Per-file Rollback

Neu mot file parse/store loi:

- du lieu cua file do se bi rollback
- file do bi tinh la `skipped`
- file khac van tiep tuc index

### Cross-file Resolution

CodeIntel v1 resolve local imports cho:

- Python `from util import helper`
- TypeScript/JavaScript `import { helper } from './mod'`

Nghia la `CALLS` co the noi toi symbol o file khac trong cung project.

## Gioi Han Hien Tai

- Khong resolve external package imports nhu `import React from 'react'`
- Khong co full type inference
- Khong phan tich dynamic dispatch
- Khong support monorepo graph phuc tap vuot qua import local co ban
- `impact` hien dua tren `CALLS` reverse graph, khong phai dependency graph tong quat

## Verification Da Chay

Da verify cac buoc sau:

- `pytest -q test_codeintel.py`
- `pytest -q test_supabrain_mcp_timeout_patch.py`
- `python -m compileall codeintel`
- Smoke test that qua PostgreSQL voi brain tam, sau do da `clear()`

## Troubleshooting

### Khong thay tools CodeIntel trong MCP client

Kiem tra:

- MCP command co tro vao [supabrain_mcp.py](C:/Users/quangda/Downloads/nmem-hub-chr/supabrain_mcp.py) khong
- editor da restart hoan toan chua
- dependencies da cai chua

### Index tra ve `No supported files found`

Nguyen nhan thuong gap:

- path sai
- repo chi co language v2 chua support
- file nam trong folder ignore nhu `node_modules`, `.git`, `vendor`

### Search ra rong sau khi index

Kiem tra:

- `project_path` truyen vao query co dung absolute path da index khong
- ban co dang o brain khac khong
- generation moi nhat co `status = active` khong

### Muon re-index sach

Dung:

```json
{
  "path": "C:\\Users\\quangda\\Downloads\\nmem-hub-chr",
  "force": true
}
```

`force` chi clear index CodeIntel cua dung project do, khong xoa toan bo brain.

## Danh Cho Van Hanh

Khuyen nghi:

- dung 1 brain rieng cho moi repo lon
- khong index truc tiep vao brain dang chua memory quan trong neu khong can
- neu can smoke test tren VPS, dung brain tam roi `clear()` sau khi test

## Developer Notes

Neu can mo rong v2, diem vao chinh la:

- [codeintel/parser.py](C:/Users/quangda/Downloads/nmem-hub-chr/codeintel/parser.py)
- [codeintel/storage.py](C:/Users/quangda/Downloads/nmem-hub-chr/codeintel/storage.py)
- [codeintel/tools.py](C:/Users/quangda/Downloads/nmem-hub-chr/codeintel/tools.py)

Test chinh:

- [test_codeintel.py](C:/Users/quangda/Downloads/nmem-hub-chr/test_codeintel.py)

Khi them relation moi, can update ca:

1. parser
2. storage/query logic neu co query moi
3. MCP tool output neu can
4. tests
