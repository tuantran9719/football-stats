# Kiến trúc

## Hai thư mục tách biệt

```
football-platform/
├── backend/     FastAPI (Python) — độc lập, không chia sẻ mã nguồn với frontend
├── frontend/    Expo (React Native / TypeScript)
└── start.sh     Khởi động cả hai cùng lúc
```

Trước đây backend viết bằng Node/TypeScript trong cùng một monorepo với
frontend, dùng chung các gói `@fb/types`, `@fb/api-client` qua npm
workspaces. Từ khi backend chuyển sang FastAPI, hai bên không còn ngôn
ngữ chung để chia sẻ mã nguồn, nên ranh giới duy nhất giữa chúng là
**hợp đồng HTTP**: đường dẫn, tham số, và hình dạng JSON.

## Hệ quả của việc tách rời

- Kiểu dữ liệu phải khai báo **hai lần**, đúng khớp nhau: một bên bằng
  Pydantic ở `backend/app/models.py`, một bên bằng TypeScript ở
  `frontend/src/types.ts`. Đổi hình dạng response ở backend mà quên sửa
  type bên frontend sẽ không bị bắt lỗi lúc biên dịch, chỉ lộ ra lúc chạy.
- Một lỗi thật đã gặp khi mới tách xong: Node cũ bỏ hẳn trường ra khỏi
  JSON khi giá trị là `undefined` (JSON.stringify tự loại bỏ), còn
  Pydantic gửi tường minh `"score": null`. Code frontend kiểm tra
  `!== undefined` cho qua giá trị `null`, gây lỗi đọc thuộc tính trên
  `null`. Bài học: mọi trường có thể rỗng ở phía Python phải được kiểm
  tra bằng `!= null` hoặc toán tử `??`/optional chaining ở frontend,
  không chỉ so sánh với `undefined`.
- Không còn kiểm tra kiểu xuyên suốt hai bên. Cách giảm rủi ro: giữ
  đúng tên trường và cấu trúc giữa hai file model, và khi đổi một bên
  thì rà lại bên kia bằng tay.

## Backend — FastAPI

```
backend/
├── app/
│   ├── main.py           route
│   ├── service.py        nghiệp vụ, nơi duy nhất gọi provider và stats
│   ├── stats.py           tính theo hiệp, trung bình N trận
│   ├── cache.py           cache trong bộ nhớ
│   ├── models.py          mô hình dữ liệu (Pydantic)
│   └── providers/
│       ├── sources.py     toàn bộ URL và mã giải đấu
│       └── espn.py        adapter cho nguồn ESPN
├── schema.sql              lược đồ PostgreSQL, chưa nối vào code
└── requirements.txt
```

Nguyên tắc adapter giữ nguyên như bản Node trước đây: mọi hiểu biết về
cấu trúc JSON của ESPN chỉ nằm trong `providers/espn.py`. Đổi nguồn dữ
liệu là viết thêm một file tương tự và đổi `get_provider()`, không đụng
tới `service.py` hay route.

## Frontend — Expo

```
frontend/
├── App.tsx
└── src/
    ├── api.ts        gọi backend qua fetch, tự dò địa chỉ mạng
    ├── types.ts       kiểu dữ liệu, khớp tay với backend/app/models.py
    ├── theme.ts
    ├── i18n/          tiếng Việt và tiếng Anh
    ├── components/ui.tsx
    └── screens/
```

Frontend không còn phụ thuộc workspace nào, `npm install` trong đúng
thư mục `frontend/` là đủ.

## Các endpoint của backend

| Đường dẫn | Công dụng |
|---|---|
| `GET /api/health` | Kiểm tra backend còn sống |
| `GET /api/leagues` | Danh sách giải đấu |
| `GET /api/teams?league=EPL` | Danh sách đội của một giải |
| `GET /api/matches?league=EPL` | Danh sách trận quanh hôm nay |
| `GET /api/matches/upcoming?league=EPL` | Các trận sắp diễn ra |
| `GET /api/matches/:id?league=EPL` | Chi tiết một trận, kèm số liệu tách theo hiệp |
| `GET /api/teams/:id/form?league=EPL&window=10` | Phong độ 5, 10, 20 trận gần nhất |
| `GET /api/h2h?league=EPL&teamA=&teamB=&window=10` | Đối đầu giữa hai đội |

## Chạy

```bash
./start.sh
```

Lần đầu cần cài backend trước:

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```
