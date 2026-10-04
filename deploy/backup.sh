#!/usr/bin/env bash
#
# Sao lưu thư mục data/ trên VPS. Chạy TRÊN VPS, nên đặt vào cron.
#
# Vì sao đáng sao lưu: data/ chứa hệ số mô hình dự đoán của 39 giải và
# bộ phân loại câu hỏi đã học từ người dùng thật. Mất thì app vẫn chạy,
# nhưng phải học lại từ đầu — hàng nghìn lượt gọi ESPN dồn vào vài phút,
# gần như chắc chắn dính chặn tần suất. Dữ liệu này không lấy lại được
# từ đâu khác.
set -euo pipefail

DIR="${DIR:-/opt/football-stats}"
OUT="${OUT:-/opt/backups}"
KEEP="${KEEP:-14}"

mkdir -p "$OUT"
STAMP="$(date +%Y%m%d-%H%M%S)"
tar -czf "$OUT/data-$STAMP.tar.gz" -C "$DIR" data

# Giữ lại KEEP bản gần nhất, xoá phần cũ hơn.
ls -1t "$OUT"/data-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "đã sao lưu: $OUT/data-$STAMP.tar.gz ($(du -h "$OUT/data-$STAMP.tar.gz" | cut -f1))"
