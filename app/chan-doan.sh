#!/usr/bin/env bash
# Chẩn đoán kết nối tới LLM self-hosted.  Chạy:  bash chan-doan.sh
cd "$(dirname "$0")" || exit 1
python3 - <<'PY'
import os, ssl, sys, socket, traceback, urllib.request, subprocess
U = "http://localhost:8000/v1/models"
print("Python :", sys.version.split()[0], "|", sys.executable)
print("OpenSSL:", ssl.OPENSSL_VERSION)
cafile = ssl.get_default_verify_paths().cafile
print("CA mặc định:", cafile or "(KHÔNG CÓ — gần như chắc chắn là nguyên nhân)")
print("SSL_CERT_FILE:", os.environ.get("SSL_CERT_FILE", "(chưa đặt)"))
px = {k: v for k, v in os.environ.items() if "proxy" in k.lower()}
print("Proxy env:", px or "(không có)")
try:
    import certifi; print("certifi:", certifi.where())
except ImportError:
    print("certifi: (chưa cài)")
print()

print("1) DNS")
try: print("   →", socket.gethostbyname("localhost"))
except Exception as e: print("   ✗", repr(e))

print("2) urllib, có xác thực chứng chỉ  (đúng cách script đang gọi)")
try:
    with urllib.request.urlopen(U, timeout=20) as r:
        print("   ✓ HTTP", r.status, "→ không có vấn đề gì, script phải chạy được")
except Exception as e:
    print("   ✗", repr(e))
    print("   reason:", repr(getattr(e, "reason", None)))
    traceback.print_exc()

print("3) urllib, KHÔNG xác thực chứng chỉ  (chỉ để chẩn đoán, không dùng khi chạy thật)")
try:
    c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(U, timeout=20, context=c) as r:
        print("   ✓ HTTP", r.status, "→ lỗi nằm gọn ở xác thực chứng chỉ, tom-tat.sh tự vá được")
except Exception as e:
    print("   ✗", repr(e), "→ lỗi KHÔNG phải do chứng chỉ, là mạng hoặc server")

print("4) curl để đối chiếu  (curl dùng kho CA hệ thống, Python thì không)")
r = subprocess.run(["curl","-sS","-o","/dev/null","-w","HTTP %{http_code}","--max-time","20",U],
                   capture_output=True, text=True)
print("  ", r.stdout or r.stderr.strip())
PY
