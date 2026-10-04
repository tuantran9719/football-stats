# Football Stats

Ứng dụng thống kê bóng đá, ưu tiên tiếng Việt. Số liệu tách theo từng
hiệp — bàn thắng, phạt góc, thẻ phạt — kèm dự đoán trước trận bằng mô
hình tự viết, không gọi dịch vụ AI nào.

## Có gì

- **39 giải đấu**: châu Âu, Nhật Bản, Trung Quốc, Úc, MLS, Nam Mỹ.
- **Thống kê theo hiệp** cho từng trận, không chỉ tổng cả trận.
- **Mô hình dự đoán Poisson có hệ số đội** (Dixon-Coles), tự huấn
  luyện lại mỗi vài tiếng và tự chấm điểm mình bằng điểm Brier trên
  những trận chưa dùng để học. Xem `backend/app/predictor/`.
- **Hỏi đáp theo từng trận**: bộ phân loại ý định tự viết, học thêm từ
  chính câu người dùng gõ. Xem `backend/app/chat/`.
- **Đội hình trên sân** kèm điểm số liệu từng cầu thủ.
- **12 ngôn ngữ.**

Không gọi AI, không có khoá API trả phí nào trong đường chạy.

## Chạy thử

```bash
# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # điền SMTP nếu cần hộp thư góp ý
.venv/bin/python -m uvicorn app.main:app --port 4000

# Frontend
cd frontend
npm install
npx expo start
```

Chạy không cần mạng, bằng dữ liệu mẫu:

```bash
DATA_PROVIDER=demo .venv/bin/python -m uvicorn app.main:app --port 4000
```

## Cấu trúc

| Thư mục | Việc |
|---|---|
| `backend/app/providers/` | Nối với nguồn dữ liệu. **Chỉ thư mục này được biết nguồn là ai** — xem README bên trong. |
| `backend/app/predictor/` | Mô hình dự đoán và phần huấn luyện. |
| `backend/app/chat/` | Bộ hỏi đáp theo trận. |
| `backend/app/rating.py` | Điểm số liệu cầu thủ. |
| `frontend/src/` | Ứng dụng Expo / React Native. |

## Đổi nguồn dữ liệu

Đặt `DATA_PROVIDER`. Thêm nguồn mới là viết một file trong
`backend/app/providers/` — không file nào khác trong dự án được nhắc
tên nguồn, và có script kiểm tra điều đó:

```bash
cd backend && python3 scripts/check_provider_seam.py
```

## Lưu ý

Bản hiện tại lấy dữ liệu từ các endpoint không có tài liệu công khai
của ESPN. Dùng để học và thử nghiệm; muốn phát hành rộng rãi thì nên
chuyển sang nguồn có giấy phép — phần `providers/` dựng sẵn cho việc đó.
