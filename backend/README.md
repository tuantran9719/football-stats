# Backend — FastAPI

Backend độc lập, tách hẳn khỏi frontend. Không còn chia sẻ mã nguồn qua
workspace monorepo; hợp đồng API (đường dẫn, hình dạng JSON) là ranh giới
duy nhất giữa hai bên.

## Cài đặt lần đầu

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Chạy

```bash
cd backend
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload
```

`--reload` để tự nạp lại khi sửa code. Bỏ cờ này khi chạy thật.

## Cấu trúc

```
backend/
├── app/
│   ├── main.py           FastAPI app + toàn bộ route
│   ├── service.py        Tầng nghiệp vụ, nơi duy nhất gọi provider và stats
│   ├── stats.py           Tính theo hiệp, trung bình N trận
│   ├── cache.py           Cache trong bộ nhớ
│   ├── models.py          Mô hình dữ liệu (Pydantic)
│   └── providers/
│       ├── sources.py     Toàn bộ URL và mã giải đấu
│       └── espn.py        Adapter cho nguồn ESPN
├── schema.sql              Lược đồ PostgreSQL, chưa nối vào code
└── requirements.txt
```

## Đổi nguồn dữ liệu

Viết file mới trong `app/providers/`, cài đặt các phương thức giống
`EspnProvider`, rồi đổi `get_provider()` trong `app/providers/espn.py`
(hoặc tách thành `app/providers/__init__.py` khi có nhiều nguồn) để trỏ
sang class mới. `app/service.py` và toàn bộ route không phải sửa gì.

## Ba điều đã kiểm chứng thực tế về ESPN, đừng đổi nếu chưa thử lại

1. ESPN trả 403 nếu User-Agent giả dạng trình duyệt.
2. Tỷ số trận chưa đá là chuỗi `"0"`, không phải để trống. Middleware
   `_to_match` chỉ gán tỷ số khi trạng thái là live, halftime, hoặc
   finished.
3. Không có tham số "N trận sắp tới". Phải đọc `leagues[0].calendar` từ
   phản hồi scoreboard để tìm ngày thi đấu tương lai.
