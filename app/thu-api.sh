#!/usr/bin/env bash
# Thử nhiều biến thể payload để tìm cái server chấp nhận.  Chạy: bash thu-api.sh
set -u
cd "$(dirname "$0")" || exit 1
: "${LLM_BASE:?Thiếu LLM_BASE. Ví dụ: export LLM_BASE=https://may-chu-cua-ban}"
[ -f .ca-bundle.pem ] && export SSL_CERT_FILE="$PWD/.ca-bundle.pem"
python3 - <<'PY'
import json, os, urllib.request, urllib.error
BASE = os.environ.get("LLM_BASE", "").rstrip("/")
MSG  = [{"role": "user", "content": "Trả lời đúng một từ: xin chào"}]

def call(name, body, path="/v1/chat/completions"):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read().decode())
            out = j.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"  ✓ {name:<34} HTTP {r.status} → {out[:60]!r}")
            return True
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")[:400]
        print(f"  ✗ {name:<34} HTTP {e.code}")
        print(f"      {body_txt}")
    except Exception as e:
        print(f"  ✗ {name:<34} {type(e).__name__}: {e}")
    return False

print("Model khả dụng:")
try:
    with urllib.request.urlopen(BASE + "/v1/models", timeout=20) as r:
        models = [m["id"] for m in json.loads(r.read())["data"]]
    print("  ", ", ".join(models))
except Exception as e:
    print("  ✗", e); models = [m] if (m := os.environ.get("LLM_MODEL")) else []

M = os.environ.get("LLM_MODEL") or (models[0] if models else "")
if not M:
    raise SystemExit("Không có model nào. Đặt LLM_MODEL.")
print(f"\nBiến thể payload (model {M}):")
call("hiện tại: max_tokens+temp+stream", {"model": M, "messages": MSG, "temperature": 0.3,
                                          "max_tokens": 300, "stream": False})
call("bỏ stream",                        {"model": M, "messages": MSG, "temperature": 0.3, "max_tokens": 300})
call("bỏ max_tokens",                    {"model": M, "messages": MSG, "temperature": 0.3})
call("max_completion_tokens",            {"model": M, "messages": MSG, "max_completion_tokens": 300})
call("tối giản (model+messages)",        {"model": M, "messages": MSG})

print("\nThử từng model, payload tối giản:")
for m in models:
    call(m, {"model": m, "messages": MSG})

print("\nThử /v1/completions (API cũ):")
call("completions", {"model": M, "prompt": "Xin chào", "max_tokens": 20}, "/v1/completions")
PY
