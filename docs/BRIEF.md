# 💡 BRIEF: Neural Memory Hub trên MikroTik CHR

**Ngày tạo:** 2026-03-24
**Loại sản phẩm:** Self-hosted Server (Docker Container trên MikroTik CHR)
**Chế độ:** Shared Server Mode (không cần local brain)

---

## 1. VẤN ĐỀ CẦN GIẢI QUYẾT

Hiện tại mỗi máy (PC, laptop) dùng Neural Memory riêng lẻ — **kiến thức không chia sẻ được** giữa các thiết bị. Cần một Hub trung tâm để tất cả máy dùng chung 1 brain duy nhất, qua domain `nmem.quangda.dpdns.org`.

## 2. GIẢI PHÁP ĐỀ XUẤT

Chạy **Neural Memory Server** (`nmem serve`) ở chế độ **Shared Server Mode** trên container MikroTik CHR. Tất cả máy trỏ thẳng vào server — **không cần local brain**.

### Tại sao Shared Server Mode?
- CHR tắt = mất internet = không làm việc được → lo offline là thừa
- Project sync qua GitHub → không cần giữ context riêng trên local
- Đơn giản nhất: 1 brain trên server, tất cả máy dùng chung

## 3. HẠ TẦNG HIỆN CÓ

| Thành phần | Chi tiết |
|-----------|----------|
| **Router** | MikroTik CHR, RouterOS v7 |
| **Domain** | `nmem.quangda.dpdns.org` (DDNS) |
| **Architecture** | x86_64 (CHR) |
| **Container support** | OCI-compliant (RouterOS v7.4+) |

## 4. KIẾN TRÚC

```
┌─────────────────────────────────────────┐
│           MikroTik CHR (RouterOS v7)    │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  Container: neural-memory-server  │  │
│  │  (Python 3.11-slim)              │  │
│  │                                   │  │
│  │  nmem serve --host 0.0.0.0       │  │
│  │        ↕ port 8000               │  │
│  │  /data/brain.db (persistent)     │  │
│  └──────────┬────────────────────────┘  │
│             │ VETH interface            │
│  ┌──────────┴────────────────────────┐  │
│  │  Bridge / DST-NAT                │  │
│  │  nmem.quangda.dpdns.org:8000     │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         ↕
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │  PC #1  │  │  PC #2  │  │ Laptop  │
   │ shared  │  │ shared  │  │ shared  │
   │ enable  │  │ enable  │  │ enable  │
   └─────────┘  └─────────┘  └─────────┘

Client setup (mỗi máy):
  nmem shared enable http://nmem.quangda.dpdns.org:8000
```

## 5. TÍNH NĂNG

### 🚀 MVP (Bắt buộc có):
- [ ] Docker image chứa `neural-memory[server]`
- [ ] Container chạy `nmem serve --host 0.0.0.0 -p 8000`
- [ ] VETH interface + Bridge trên MikroTik CHR
- [ ] DST-NAT rule → container port 8000
- [ ] Persistent storage cho brain data (bind-mount)
- [ ] Client: `nmem shared enable` trỏ đến server

### 🎁 Phase 2 (Làm sau):
- [ ] HTTPS + API key (nếu truy cập ngoài LAN)
- [ ] Auto-restart container khi CHR reboot
- [ ] Backup tự động brain data

## 6. ƯỚC TÍNH SƠ BỘ

| Mục | Đánh giá |
|-----|----------|
| **Độ phức tạp** | Đơn giản - Trung bình |
| **Thời gian** | ~1 ngày setup |
| **Yêu cầu CHR** | RAM ≥ 256MB, Disk ≥ 500MB |

### ⚠️ Rủi ro:
- **Python image size**: ~150-200MB, cần đủ disk trên CHR
- **Không có Docker Compose**: Cấu hình container qua RouterOS CLI
- **Reboot persistence**: Phải bind-mount đúng thư mục data

## 7. CÁC FILE CẦN TẠO

```
nmem-hub-chr/
├── docs/BRIEF.md              ← (file này)
├── Dockerfile                  ← Build image nmem-hub
├── entrypoint.sh               ← Script khởi động
├── mikrotik/setup-container.rsc ← RouterOS script
└── README.md                   ← Hướng dẫn triển khai
```

## 8. BƯỚC TIẾP THEO

→ Chạy `/plan` để thiết kế chi tiết từng file và cấu hình MikroTik
