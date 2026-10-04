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

## Bước 1 — Mã nguồn đã nằm trên GitHub

Repo riêng tư: `tuantran9719/football-stats`, nhánh `main`.

Đây là **monorepo**: backend và frontend nằm chung một repo. Điều này
đổi cách cấu hình Railway ở bước sau — đọc kỹ phần "Root Directory".

## Bước 2 — Tạo dịch vụ trên Railway

1. https://railway.app → đăng nhập bằng GitHub.
2. **New Project → Deploy from GitHub repo → `football-stats`.**
3. **Settings → Root Directory → gõ `backend`.**

   Bước 3 là bước dễ bỏ sót nhất và là chỗ hỏng thường gặp nhất. Railway
   mặc định build từ gốc repo; ở đó không có `requirements.txt`, chỉ có
   thư mục `frontend/` chứa `package.json`. Nixpacks sẽ tưởng đây là dự
   án Node, đi build ứng dụng Expo, rồi báo lỗi không hiểu nổi — hoặc tệ
   hơn là build "thành công" mà chẳng có máy chủ nào chạy.

   Đặt Root Directory thành `backend` thì Railway mới thấy
   `requirements.txt`, `.python-version` và `railway.json`.

4. **Settings → Networking → Generate Domain** để lấy tên miền công khai.

## Bước 3 — Gắn ổ đĩa lưu lâu dài (ĐỪNG BỎ QUA)

**Variables → New Volume**, mount vào `/data`. Rồi thêm biến:

```
DATA_DIR                /data
```

Trước đây phần này ghi là tuỳ chọn. **Giờ thì không.** Thư mục `data/`
nay chứa hai thứ đắt giá:

- `predictor.json` — hệ số mô hình dự đoán của 39 giải.
- `chat_model.json` — bộ phân loại câu hỏi đã học (khoảng 500 KB).

Không có ổ đĩa thì mỗi lần deploy lại là mất sạch, và máy chủ phải học
lại từ đầu: tải lịch 4 mùa của từng đội ở từng giải, hàng nghìn lượt gọi
ESPN dồn vào vài phút. Gần như chắc chắn dính chặn tần suất, và lúc đó
người dùng thật đang mở app sẽ thấy "Nguồn dữ liệu đang bận".

## Bước 3b — Khai biến môi trường

Trong **Variables**, thêm 5 biến này (lấy giá trị từ `backend/.env` ở
máy). **Không** đưa file `.env` lên git.

Từ khi mô hình dự đoán tự viết thay hẳn phần AI, **không còn cần
`ANTHROPIC_API_KEY` hay `GEMINI_API_KEY`**. Đừng đưa chúng lên máy chủ:
khoá không dùng tới mà vẫn nằm trên dịch vụ của bên thứ ba chỉ là rủi ro
thừa.

```
FEEDBACK_SMTP_HOST      smtp.gmail.com
FEEDBACK_SMTP_PORT      587
FEEDBACK_SMTP_USER      (địa chỉ Gmail dùng để gửi)
FEEDBACK_SMTP_PASS      (mật khẩu ứng dụng 16 ký tự)
FEEDBACK_TO             (địa chỉ nhận góp ý)
```

Không khai `FEEDBACK_TO` thì góp ý gửi về chính `FEEDBACK_SMTP_USER`.

Một biến tuỳ chọn nữa:

```
DATA_PROVIDER           espn        (mặc định; đặt demo để chạy bằng dữ liệu mẫu)
```

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
