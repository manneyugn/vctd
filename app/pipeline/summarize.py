#!/usr/bin/env python3
"""Buoc 5: tom tat tung chuong bang LLM self-hosted (OpenAI-compatible).

Chi dung thu vien chuan. Co checkpoint nen dung giua chung chay lai khong mat gi.

  python3 pipeline/summarize.py --probe
  python3 pipeline/summarize.py --model <ten-model> --concurrency 4
  python3 pipeline/summarize.py --limit 5            # chay thu 5 chuong
"""
import argparse, gzip, json, os, random, re, sys, threading, time
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
CKPT = DATA / "summaries.partial.jsonl"
LOI  = DATA / "summaries-errors.jsonl"   # nhat ky loi de chan doan

DEFAULT_BASE = "http://localhost:8000"
PROMPT = """Tóm tắt chương truyện tiên hiệp dưới đây bằng 2-3 câu tiếng Việt.
Nêu rõ: nhân vật xuất hiện, sự kiện chính, kết quả. Không bình luận, không mở đầu bằng "Chương này".
Chỉ trả về phần tóm tắt, không thêm gì khác.

---
{text}
---"""

lock = threading.Lock()
done = {"n": 0, "fail": 0, "streak": 0, "t0": time.time()}
STOP = threading.Event()


def http_json(url, payload=None, timeout=420, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300].replace("\n", " ")
        raise RuntimeError(f"HTTP {e.code}: {detail}") from None


def probe(base, headers):
    print(f"Dò endpoint: {base}\n")
    for path, label in [("/v1/models", "OpenAI-compatible (llama.cpp / vLLM / LM Studio)"),
                        ("/api/tags", "Ollama native"),
                        ("/props", "llama.cpp server")]:
        try:
            j = http_json(base.rstrip("/") + path, timeout=20, headers=headers)
            print(f"  ✓ {path:<12} → {label}")
            if path == "/v1/models":
                for m in j.get("data", [])[:20]:
                    print(f"      model: {m.get('id')}")
            elif path == "/api/tags":
                for m in j.get("models", [])[:20]:
                    print(f"      model: {m.get('name')}")
            else:
                print(f"      {json.dumps(j)[:200]}")
        except urllib.error.HTTPError as e:
            print(f"  · {path:<12} → HTTP {e.code}")
        except Exception as e:
            print(f"  · {path:<12} → {type(e).__name__}: {e} | reason={getattr(e, 'reason', None)!r}")


DAU_HIEU_RAC = ("we need", "user asks", "need produce", "let me", "the user",
                "okay,", "<think", "we should", "i need to", "first,")
CO_DAU_VI = re.compile(r"[àáâãèéêìíòóôõùúýăđĩũơưạảấầẩậắằẳặẹẻẽếềểệỉịọỏốồổộớờởợụủứừửựỳỵỷỹ]", re.I)

def hop_le(msg):
    """Tom tat dat yeu cau? Tra ve (ok, ly_do)."""
    if len(msg) < 60:
        return False, f"quá ngắn ({len(msg)} ký tự)"
    if len(msg) > 1200:
        return False, f"quá dài ({len(msg)} ký tự) — nhiều khả năng là vệt suy nghĩ"
    dau = msg[:250].lower()
    for m in DAU_HIEU_RAC:
        if m in dau:
            return False, f"lẫn văn bản suy nghĩ ({m!r})"
    if not CO_DAU_VI.search(msg):
        return False, "không phải tiếng Việt"
    return True, ""


def summarize_one(base, model, headers, text, retries=4):
    url = base.rstrip("/") + "/v1/chat/completions"
    last = None
    for attempt in range(retries):
        # qwen3 la model reasoning. finish_reason=length + content rong = het cho
        # giua chung phan nghi, nen moi lan thu lai phai NOI THEM cho, goi lai
        # y nguyen chi lap lai that bai.
        body = {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT.format(text=text[:12000])}],
            "temperature": 0.3,
            "max_tokens": [8000, 14000, 22000, 32000][min(attempt, 3)],
        }
        try:
            j = http_json(url, body, headers=headers)
            choice = j["choices"][0]
            m = choice.get("message", {})
            # KHONG lay reasoning_content: do la vet suy nghi, khong phai tom tat.
            # Rong = that bai -> retry, chu khong luu rac vao checkpoint.
            msg = (m.get("content") or "").strip()
            msg = re.sub(r"<think>.*?</think>", "", msg, flags=re.S).strip()
            msg = re.sub(r"^(Tóm tắt|TÓM TẮT)\s*:\s*", "", msg).strip()
            ok, vi_sao = hop_le(msg)
            if ok:
                return msg
            last = f"{vi_sao} (finish_reason={choice.get('finish_reason')})"
        except Exception as e:
            last = f"{type(e).__name__}: {e} | reason={getattr(e, 'reason', None)!r}"
            time.sleep(min(30, 2 ** attempt) + random.random())
    raise RuntimeError(last)


def iter_chapters(limit=None):
    meta = json.loads((DATA / "chapters.json").read_text(encoding="utf-8"))
    cache, out = {}, []
    for ch in meta["chapters"]:
        sid = ch["s"]
        if sid not in cache:
            cache.clear()
            with gzip.open(DATA / f"shard-{sid:03d}.json.gz", "rt", encoding="utf-8") as f:
                cache[sid] = json.load(f)
        out.append((ch["n"], ch["t"], "\n".join(cache[sid][str(ch["n"])])))
        if limit and len(out) >= limit:
            break
    return out


def don_checkpoint():
    """Loc bo cac ban ghi hong; chay lai se tu lam lai dung nhung chuong do."""
    if not CKPT.exists():
        print("Chưa có checkpoint."); return
    giu, bo = [], []
    for line in CKPT.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        ok, vi_sao = hop_le(r.get("s", ""))
        (giu if ok else bo).append((r, vi_sao if not ok else ""))
    # KHONG ghi de ban sao luu cu: lan dau moi luu, de con doi chung ve sau
    bak = CKPT.with_suffix(".jsonl.bak")
    if bak.exists():
        import time as _t
        bak = CKPT.with_suffix(f".jsonl.bak.{int(_t.time())}")
    bak.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r, _ in giu + bo) + "\n", encoding="utf-8")
    CKPT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r, _ in giu), encoding="utf-8")
    from collections import Counter
    ly_do = Counter(v.split(" (")[0] for _, v in bo)
    print(f"giữ lại : {len(giu)} chương")
    print(f"loại bỏ : {len(bo)} chương  → {dict(ly_do)}")
    print(f"chương cần chạy lại: {sorted(r['n'] for r, _ in bo)[:25]}{' …' if len(bo) > 25 else ''}")
    print(f"(bản gốc lưu ở {bak.name})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE", DEFAULT_BASE))
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "qwen3.8"))
    ap.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", ""))
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--clean", action="store_true",
                    help="Xoá các bản tóm tắt hỏng khỏi checkpoint để chạy lại")
    a = ap.parse_args()

    headers = {"Authorization": f"Bearer {a.api_key}"} if a.api_key else {}

    if a.probe:
        probe(a.base_url, headers)
        return

    if not a.model:
        try:
            j = http_json(a.base_url.rstrip("/") + "/v1/models", timeout=20, headers=headers)
            a.model = j["data"][0]["id"]
            print(f"Tự chọn model: {a.model}")
        except Exception as e:
            sys.exit(f"Không lấy được danh sách model ({e}). Truyền --model.")

    if a.clean:
        don_checkpoint()
        return

    have = {}
    if CKPT.exists():
        for line in CKPT.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line); have[r["n"]] = r["s"]
            except Exception:
                pass
        print(f"Checkpoint: đã có {len(have)} chương.")

    chapters = [c for c in iter_chapters(a.limit or None) if c[0] not in have]
    total = len(chapters)
    print(f"Cần tóm tắt: {total} chương · model {a.model} · {a.concurrency} luồng\n")
    if not total:
        print("Không còn gì để làm.")
    ck = CKPT.open("a", encoding="utf-8")

    def work(item):
        if STOP.is_set():
            return
        n, title, text = item
        try:
            s = summarize_one(a.base_url, a.model, headers, text)
            with lock:
                ck.write(json.dumps({"n": n, "s": s, "t": int(time.time())},
                                    ensure_ascii=False) + "\n"); ck.flush()
                have[n] = s
                done["n"] += 1
                done["streak"] = 0
        except Exception as e:
            with lock:
                with LOI.open("a", encoding="utf-8") as lf:
                    lf.write(json.dumps({"n": n, "t": int(time.time()),
                                         "err": str(e)[:400]}, ensure_ascii=False) + "\n")
                done["fail"] += 1
                done["streak"] += 1
                print(f"  ✗ c.{n}: {e}", file=sys.stderr)
                if done["streak"] >= 8 and done["n"] == 0 and not STOP.is_set():
                    STOP.set()
                    print("\n⛔ 8 lần liên tiếp đều lỗi, dừng sớm để khỏi chạy vô ích."
                          "\n   Lỗi lặp lại ở trên cho biết server trả về cái gì.", file=sys.stderr)
        with lock:
            k = done["n"] + done["fail"]
            if k % 10 == 0 or k == total:
                el = time.time() - done["t0"]
                rate = k / el if el else 0
                eta = (total - k) / rate if rate else 0
                print(f"  {k}/{total} · {rate:.2f} ch/s · còn ~{eta/60:.0f} phút · lỗi {done['fail']}", flush=True)

    if total:
        with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
            list(ex.map(work, chapters))
    ck.close()

    with gzip.open(DATA / "summaries.json.gz", "wt", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in sorted(have.items())}, f,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"\n✓ {len(have)} tóm tắt → web/data/summaries.json.gz (lỗi: {done['fail']})")


if __name__ == "__main__":
    main()
