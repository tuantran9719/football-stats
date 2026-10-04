#!/bin/bash
# Khởi động backend (FastAPI) và frontend (Expo) cùng lúc.
# Dùng: ./start.sh
set -e
cd "$(dirname "$0")"

# Tìm Node: ưu tiên bản cài sẵn trong hệ thống, nếu không có thì dùng bản tải riêng.
if command -v node >/dev/null 2>&1; then
  NODE_BIN="$(dirname "$(command -v node)")"
elif [ -x "$HOME/.local/node/bin/node" ]; then
  NODE_BIN="$HOME/.local/node/bin"
else
  echo "Không tìm thấy Node. Cài bằng: brew install node"
  exit 1
fi
export PATH="$NODE_BIN:$PATH"
echo "Node: $(node --version)"

if [ ! -x "backend/.venv/bin/uvicorn" ]; then
  echo "Backend chưa cài. Chạy trước:"
  echo "  cd backend && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Dọn tiến trình cũ để khỏi trùng cổng.
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "expo start" 2>/dev/null || true
sleep 1

echo ""
echo "1/2  Khởi động backend (FastAPI) tại cổng 4000..."
(cd backend && ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 4000 > /tmp/football-api.log 2>&1 &)

for i in $(seq 1 30); do
  sleep 1
  if curl -s --max-time 3 http://localhost:4000/api/health >/dev/null 2>&1; then
    echo "     Backend đã sẵn sàng."
    break
  fi
  if [ "$i" = "30" ]; then
    echo "     Backend không lên được. Xem log: tail -50 /tmp/football-api.log"
    exit 1
  fi
done

echo ""
echo "2/2  Khởi động frontend..."
echo ""
echo "  Xem trên trình duyệt:  bấm phím  w  khi Metro hiện menu"
echo "  Xem trên điện thoại:   cài Expo Go rồi quét mã QR hiện ra"
echo "  Dừng lại:              bấm Ctrl + C"
echo ""

cd frontend
npx expo start
