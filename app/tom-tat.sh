#!/usr/bin/env bash
# Tóm tắt 4211 chương bằng LLM self-hosted.  Chạy:  bash tom-tat.sh  [số_luồng]
set -u
cd "$(dirname "$0")" || exit 1
LUONG="${1:-4}"
URL="${LLM_BASE:?Thiếu LLM_BASE. Ví dụ: export LLM_BASE=https://may-chu-cua-ban}/v1/models"
BUNDLE="$PWD/.ca-bundle.pem"

thu_ket_noi() {   # $1 = file CA (rỗng = dùng mặc định của Python)
  SSL_CERT_FILE="${1:-}" python3 - "$URL" <<'PY' 2>/dev/null
import os, sys, urllib.request
if not os.environ.get("SSL_CERT_FILE"): os.environ.pop("SSL_CERT_FILE", None)
try:
    urllib.request.urlopen(sys.argv[1], timeout=20); sys.exit(0)
except Exception: sys.exit(1)
PY
}

echo "=== Kiểm tra chứng chỉ ==="
if [ -n "${SSL_CERT_FILE:-}" ] && thu_ket_noi "$SSL_CERT_FILE"; then
  echo "✓ Dùng SSL_CERT_FILE bạn đã đặt sẵn: $SSL_CERT_FILE"
elif thu_ket_noi ""; then
  echo "✓ Python đã tin chứng chỉ sẵn, không cần làm gì."
else
  # Server dùng CA nội bộ. curl tin được vì đọc keychain macOS; Python thì không.
  # Dựng bundle = CA công cộng (certifi) + toàn bộ CA trong keychain của máy.
  echo "• Chứng chỉ do CA nội bộ ký. Đang dựng bundle từ keychain macOS…"
  : > "$BUNDLE"
  python3 -c "import certifi,sys,shutil; shutil.copyfileobj(open(certifi.where()),sys.stdout)" >> "$BUNDLE" 2>/dev/null
  for K in /System/Library/Keychains/SystemRootCertificates.keychain \
           /Library/Keychains/System.keychain \
           "$HOME/Library/Keychains/login.keychain-db"; do
    [ -e "$K" ] && security find-certificate -a -p "$K" >> "$BUNDLE" 2>/dev/null
  done
  echo "  → $(grep -c 'BEGIN CERTIFICATE' "$BUNDLE") chứng chỉ trong $BUNDLE"

  if thu_ket_noi "$BUNDLE"; then
    export SSL_CERT_FILE="$BUNDLE"
    echo "✓ Bundle hoạt động, vẫn xác thực đầy đủ."
  else
    echo
    echo "✗ Keychain không có CA nội bộ. Bạn có thư mục ~/cert — nếu CA nằm trong đó:"
    echo "    cat ~/cert/<ten-ca>.crt >> $BUNDLE"
    echo "    SSL_CERT_FILE=$BUNDLE bash tom-tat.sh"
    echo "  (không tắt xác thực chứng chỉ, chỉ thêm CA của bạn vào danh sách tin cậy)"
    exit 1
  fi
fi

echo
echo "=== Dò endpoint ==="
python3 pipeline/summarize.py --probe || exit 1

echo
echo "=== Dọn bản tóm tắt hỏng trong checkpoint ==="
python3 pipeline/summarize.py --clean

echo
echo "=== Tóm tắt 4211 chương · $LUONG luồng ==="
echo "    Ctrl-C bất cứ lúc nào, checkpoint tự lưu, chạy lại là nối tiếp."
echo
python3 pipeline/summarize.py --concurrency "$LUONG"
