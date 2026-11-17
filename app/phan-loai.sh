#!/usr/bin/env bash
# Phân loại thực thể còn ở nhóm "Khác" bằng LLM.  Chạy:  bash phan-loai.sh [số_luồng]
set -u
cd "$(dirname "$0")" || exit 1
[ -f .ca-bundle.pem ] && export SSL_CERT_FILE="$PWD/.ca-bundle.pem"
echo "=== Phân loại thực thể bằng LLM ==="
python3 pipeline/phan_loai_ai.py --concurrency "${1:-4}" || exit 1
echo
python3 pipeline/phan_loai_ai.py --apply
