#!/bin/bash
#
# Bật toàn bộ hệ thống bằng một lệnh: backend, máy chủ web, đường hầm.
#
#   ./scripts/start.sh          chỉ chạy trong mạng nội bộ
#   ./scripts/start.sh --public thêm đường hầm ngrok để chia sẻ ra ngoài
#
# Ba tiến trình, ba vai trò:
#   4000  backend FastAPI
#   5599  máy chủ web, kiêm chuyển tiếp /api sang 4000
#   ngrok đưa cổng 5599 ra tên miền công khai cố định
#
# Chỉ cần MỘT đường hầm vì máy chủ web đã gộp cả API về cùng một gốc.
# Nhờ vậy bản build web không chứa địa chỉ nào, đổi tên miền không phải
# build lại.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="/tmp/fb-web"
NGROK_DOMAIN="salvaging-garage-moneybags.ngrok-free.dev"
PUBLIC=0
[ "${1:-}" = "--public" ] && PUBLIC=1

kill_port() {
  local pids
  pids="$(lsof -ti:"$1" 2>/dev/null)"
  [ -n "$pids" ] && echo "$pids" | xargs kill -9 2>/dev/null
  return 0
}

echo "==> Dọn tiến trình cũ"
kill_port 4000
kill_port 5599
pkill -9 -f ngrok 2>/dev/null
sleep 2

echo "==> Backend (cổng 4000)"
cd "$ROOT/backend" || exit 1
# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 4000 > /tmp/fb-backend.log 2>&1 &

for _ in $(seq 1 30); do
  curl -sf http://localhost:4000/api/health > /dev/null 2>&1 && break
  sleep 1
done
curl -sf http://localhost:4000/api/health > /dev/null 2>&1 \
  && echo "    sẵn sàng" \
  || { echo "    LỖI: backend không lên, xem /tmp/fb-backend.log"; exit 1; }

if [ ! -d "$WEB_DIR" ]; then
  echo "==> Chưa có bản build web, đang build (vài phút)"
  cd "$ROOT/frontend" || exit 1
  # --clear là BẮT BUỘC: thiếu nó Metro dùng lại bản dịch đã cache và
  # biến môi trường không được nhúng vào bundle.
  EXPO_PUBLIC_API_BASE=same-origin npx expo export \
    --platform web --output-dir "$WEB_DIR" --clear > /tmp/fb-build.log 2>&1 \
    || { echo "    LỖI build, xem /tmp/fb-build.log"; exit 1; }
fi

echo "==> Máy chủ web (cổng 5599)"
nohup python3 "$ROOT/scripts/serve.py" "$WEB_DIR" 5599 > /tmp/fb-web.log 2>&1 &
sleep 2
curl -sf http://localhost:5599/api/health > /dev/null 2>&1 \
  && echo "    sẵn sàng, chuyển tiếp /api chạy tốt" \
  || echo "    CẢNH BÁO: chuyển tiếp /api chưa thông"

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || echo 'không rõ')"
echo
echo "  Máy này   http://localhost:5599"
echo "  Điện thoại http://$LAN_IP:5599   (cùng WiFi)"

if [ "$PUBLIC" = "1" ]; then
  echo
  echo "==> Đường hầm ngrok"
  nohup ngrok http 5599 --url="$NGROK_DOMAIN" --log stdout --log-format json \
    > /tmp/ngrok.log 2>&1 &
  sleep 8
  if curl -sf "https://$NGROK_DOMAIN/api/health" > /dev/null 2>&1; then
    echo "  Công khai https://$NGROK_DOMAIN"
    echo "  (lần đầu mỗi trình duyệt sẽ thấy trang cảnh báo của ngrok, bấm Visit Site)"
  else
    echo "  LỖI: đường hầm không lên, xem /tmp/ngrok.log"
  fi
fi
echo
echo "Dừng tất cả:  ./scripts/stop.sh"
