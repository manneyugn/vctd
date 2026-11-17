#!/usr/bin/env bash
# Chay web app tra cuu Van Co Than De (cuc bo, khong can internet)
cd "$(dirname "$0")/web" || exit 1
PORT="${1:-8731}"
echo "→ http://127.0.0.1:$PORT"
exec python3 -m http.server "$PORT"
