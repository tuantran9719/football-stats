#!/usr/bin/env bash
#
# Đẩy một phiên bản mới lên VPS. Chạy ở MÁY CỦA BẠN, không phải trên VPS.
#
# Vì sao build bản web ở máy chứ không trên máy chủ: Metro cần 1–1,5 GB
# RAM lúc đóng gói, và node_modules nặng 354 MB. Trên VPS 2 GB đang chạy
# sẵn hai container thì rất dễ bị nhân hệ điều hành giết giữa chừng.
# Máy chủ chỉ cần chạy Python và Caddy — nhẹ và ít thứ hỏng.
#
#   ./deploy/deploy.sh user@1.2.3.4
#
set -euo pipefail

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
    echo "Dùng: ./deploy/deploy.sh user@dia-chi-vps" >&2
    exit 1
fi

REMOTE_DIR="${REMOTE_DIR:-/opt/football-stats}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Build bản web ở máy"
cd "$ROOT/frontend"
# same-origin: bundle KHÔNG nhúng địa chỉ máy chủ nào. Caddy phục vụ web
# và chuyển tiếp /api trên cùng tên miền, nên đổi tên miền về sau không
# phải build lại.
#
# --clear là bắt buộc: thiếu nó Metro dùng lại bản dịch đã cache và địa
# chỉ cũ vẫn nằm trong bundle.
EXPO_PUBLIC_API_BASE=same-origin npx expo export \
    --platform web --output-dir "$ROOT/web" --clear

echo "==> Đẩy mã nguồn và bản web lên $TARGET:$REMOTE_DIR"
ssh "$TARGET" "mkdir -p $REMOTE_DIR"

# --delete cho thư mục web để file của bản cũ không nằm lại.
rsync -az --delete "$ROOT/web/" "$TARGET:$REMOTE_DIR/web/"
rsync -az --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude 'data' --exclude '.env' \
    "$ROOT/backend/" "$TARGET:$REMOTE_DIR/backend/"
rsync -az "$ROOT/deploy/" "$TARGET:$REMOTE_DIR/deploy/"
rsync -az "$ROOT/docker-compose.yml" "$TARGET:$REMOTE_DIR/"

echo "==> Build lại và khởi động trên máy chủ"
ssh "$TARGET" "cd $REMOTE_DIR && docker compose up -d --build"

echo "==> Chờ máy chủ sẵn sàng"
ssh "$TARGET" "cd $REMOTE_DIR && timeout 90 sh -c 'until docker compose exec -T api python -c \"import urllib.request;urllib.request.urlopen(\\\"http://127.0.0.1:4000/api/health\\\",timeout=3)\" 2>/dev/null; do sleep 3; done'"

echo "==> Xong."
ssh "$TARGET" "cd $REMOTE_DIR && docker compose ps"
