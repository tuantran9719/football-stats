# Đưa backend lên máy chủ chạy 24/7

Bản app trên CH Play **không thể** gọi về máy cá nhân. Đây là việc phải
làm trước mọi thứ khác.

## Đã chuẩn bị sẵn

| File | Việc |
|---|---|
| `requirements.txt` | Ghim phiên bản chính xác, đã thử cài sạch và chạy được |
| `.python-version` | Chốt Python 3.13 |
| `Procfile` | Lệnh chạy, tự nhận cổng `$PORT` máy chủ cấp |
| `railway.json` | Cấu hình Railway kèm health check `/api/health` |
| `render.yaml` | Cấu hình Render, dùng nếu chọn Render |
| `.gitignore` | Chặn `.env` và `data/` lọt lên git |

## Bước 1 — Đưa mã nguồn lên GitHub

Backend hiện **chưa nằm trong git**. Từ thư mục `football-platform`:

```bash
cd backend
git init
git add .
git commit -m "Backend Football Stats"
gh repo create football-stats-api --private --source=. --push
```

`.env` và `data/` đã bị `.gitignore` chặn — khoá API không lọt lên.

## Bước 2 — Tạo dịch vụ

**Railway** (khuyến nghị — có ổ đĩa lưu lâu dài):
1. https://railway.app → New Project → Deploy from GitHub repo
2. Chọn `football-stats-api`
3. Settings → Networking → Generate Domain

**Render** (miễn phí nhưng ngủ sau 15 phút không ai dùng):
1. https://render.com → New → Web Service → kết nối repo
2. Render tự đọc `render.yaml`

## Bước 3 — Khai biến môi trường

Trong bảng điều khiển của dịch vụ, thêm đúng 5 biến này (lấy giá trị từ
`backend/.env` ở máy). **Không** copy file `.env` lên git.

Từ khi mô hình dự đoán tự viết thay hẳn phần AI, **không còn cần
`ANTHROPIC_API_KEY` hay `GEMINI_API_KEY`**. Đừng đưa chúng lên máy chủ:
khoá không dùng tới mà vẫn nằm trên dịch vụ của bên thứ ba chỉ là rủi ro
thừa.

```
FEEDBACK_SMTP_HOST      smtp.gmail.com
FEEDBACK_SMTP_PORT      587
FEEDBACK_SMTP_USER      tranhuutuan9719@gmail.com
FEEDBACK_SMTP_PASS      (mật khẩu ứng dụng 16 ký tự)
FEEDBACK_TO             tranhuutuan9719@gmail.com
```

Thêm một biến nữa **nếu** có gắn ổ đĩa (Railway → Volumes, mount vào
`/data`):

```
DATA_DIR                /data
```

Không gắn ổ đĩa thì app vẫn chạy bình thường, chỉ là mỗi lần deploy lại
sẽ mất: cache AI (không sao, gọi lại), thống kê trọng tài (tự tích luỹ
lại), và file góp ý — nhưng **mọi góp ý đều đã được gửi qua email** nên
vẫn còn bản lưu trong hộp thư.

## Bước 4 — Kiểm tra

```bash
curl https://<tên-miền-của-bạn>/api/health
curl "https://<tên-miền-của-bạn>/api/matches?league=EPL"
```

`/api/health` trả về cả tình trạng cache và việc ESPN có đang chặn không.

## Bước 5 — Trỏ app sang máy chủ mới

```bash
cd ../frontend
EXPO_PUBLIC_API_BASE=https://<tên-miền-của-bạn> \
  npx expo export --platform web --output-dir /tmp/fb-web --clear
```

Cờ `--clear` là **bắt buộc**: thiếu nó Metro dùng lại bản dịch đã cache
và địa chỉ cũ vẫn nằm trong bundle.

## Lưu ý khi đã lên mạng công khai

- **ESPN chặn theo IP.** Máy chủ thuê dùng IP chung với hàng nghìn app
  khác nên dễ dính giới hạn hơn IP nhà. Cầu dao 429 và cơ chế trả bản
  cũ đã có sẵn, nhưng nên theo dõi `espn.rateLimited` ở `/api/health`.
- **Hạn mức AI.** Gemini bản miễn phí 20 lượt/ngày — vài chục người
  dùng là hết. Phải nạp tiền hoặc tắt tính năng AI trước khi phát hành.
