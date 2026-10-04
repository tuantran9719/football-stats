#!/bin/bash
# Tắt mọi tiến trình do start.sh bật lên.
set -u
for port in 4000 5599; do
  pids="$(lsof -ti:"$port" 2>/dev/null)"
  [ -n "$pids" ] && echo "$pids" | xargs kill -9 2>/dev/null
done
pkill -9 -f ngrok 2>/dev/null
pkill -9 -f cloudflared 2>/dev/null
echo "Đã dừng backend, máy chủ web và đường hầm."
