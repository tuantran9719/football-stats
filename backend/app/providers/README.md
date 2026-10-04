# Đổi nguồn dữ liệu

## Việc cần làm khi ESPN bị chặn

```bash
DATA_PROVIDER=demo
```

Đặt biến đó rồi khởi động lại máy chủ. Không sửa dòng mã nào. App mở
được, mọi màn hình vẫn vào được, chỉ là dữ liệu mẫu — hơn hẳn màn hình
trắng kèm lỗi.

Đó là đường lùi tạm. Đường thật là viết một nguồn mới.

## Viết một nguồn mới

Ba bước, không có bước thứ tư:

1. Tạo `app/providers/<tên>.py`, viết một lớp có đủ các hàm trong
   `base.py`. Nhìn `demo.py` làm mẫu — nó ngắn và đủ.
2. Thêm đúng một dòng vào `_FACTORIES` trong `__init__.py`.
3. Thêm tên nguồn vào `NAMES` trong `scripts/check_provider_seam.py`.

Rồi `DATA_PROVIDER=<tên>`.

## Hợp đồng

Chín hàm, mô tả đầy đủ trong `base.py`:

| Hàm | Trả về |
|---|---|
| `catalogue()` | những giải nguồn này phục vụ |
| `list_matches` | trận theo ngày |
| `list_upcoming_matches` | trận sắp đá |
| `list_calendar` | những ngày có trận |
| `list_teams` | danh sách đội |
| `list_team_matches` | lịch của một đội |
| `list_standings` | bảng xếp hạng |
| `list_news` | tin tức (trả rỗng cũng được) |
| `get_match_detail` | chi tiết một trận |
| `health()` | tình trạng, hiện ở `/api/health` |

Thiếu dữ liệu thì trả rỗng, đừng ném lỗi: tầng trên đã xử lý rỗng ở
mọi màn hình.

## Quy tắc bất di bất dịch

**Không file nào ngoài thư mục này được nhắc tên nguồn.** Không
`f"espn:{id}"`, không `from .providers.espn import ...`, không chuỗi
"ESPN" trong câu trả lời cho người dùng.

Dùng thay thế:

| Thay vì | Dùng |
|---|---|
| `f"espn:{id}"` | `providers.team_ref(id)` |
| `from .providers.espn import get_provider` | `from .providers import get_provider` |
| `from .providers.sources import LEAGUES` | `providers.leagues_map()` |
| viết "ESPN" trong câu trả lời | truyền `provider_name()` vào |

Kiểm tra bằng:

```bash
python3 scripts/check_provider_seam.py
```

Chạy nó trước mỗi lần phát hành. Ranh giới kiểu này luôn mục dần vì
viết tắt một lần thì mọi thứ vẫn chạy — nó chỉ nổ vào đúng ngày phải
đổi nguồn, tức ngày tệ nhất.

## Những gì đổi nguồn KHÔNG mang theo được

- **Đội yêu thích** người dùng đã lưu. Mã đội của hai nguồn không trùng
  nhau. Tiền tố khiến mã cũ không khớp nữa — cố ý, vì khớp nhầm sang
  một đội khác còn tệ hơn mất.
- **Hệ số mô hình dự đoán** trong `data/predictor.json`. Mã đội đổi thì
  phải học lại từ đầu, mất một chu kỳ huấn luyện.
- **Lịch sử bảng xếp hạng và cache**. Tự dựng lại sau vài phút.
