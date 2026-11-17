#!/usr/bin/env python3
"""Buoc 8: nho LLM phan loai cac thuc the con lai o nhom "Khac".

Mau ngu canh chi phan loai duoc nhung muc co du dan chung ro rang. Phan con lai
can doc hieu, nen hoi LLM — dua kem cau trich tu tom tat lam ngu canh.

Gui theo lo 10 thuc the moi lan goi, nen ~1800 muc chi ton ~180 luot.

  python3 pipeline/phan_loai_ai.py --limit 30     # chay thu
  python3 pipeline/phan_loai_ai.py                # chay het
  python3 pipeline/phan_loai_ai.py --apply        # ghi ket qua vao index.json.gz
"""
import argparse, gzip, json, os, random, re, sys, threading, time
import urllib.request, urllib.error
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
CKPT = DATA / "kind-ai.partial.jsonl"
LOI  = DATA / "kind-ai-errors.jsonl"

LOAI = {
    "nhan_vat":  "người, yêu thú, sinh linh có tên — bất cứ ai hành động, nói năng",
    "the_luc":   "môn phái, gia tộc, chủng tộc, quân đội, tổ chức, quốc gia",
    "dia_danh":  "nơi chốn: giới, thành, núi, biển, cung điện, bí cảnh",
    "cong_phap": "công pháp, thần thông, kiếm pháp, tâm pháp, trận pháp",
    "bao_vat":   "vũ khí, pháp bảo, đan dược, vật phẩm",
    "canh_gioi":  "cấp bậc tu luyện, cảnh giới, phẩm cấp",
    "khac":      "không thuộc nhóm nào ở trên, hoặc không đủ căn cứ để quyết",
}
LO = 3          # lo cang nho, model cang it phai nghi, cang kip truoc nginx
DAU_VI = re.compile(r"[À-ỹ]", re.I)
lock = threading.Lock()
dem = {"ok": 0, "loi": 0, "t0": time.time()}


def http_json(url, payload, headers, timeout=110):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}") from None


def hoa_ten(t):
    return " ".join(w[:1].upper() + w[1:] for w in t.split(" "))


def chua_ten(cau, ten):
    """Giu nguyen dau, chi ha chu hoa, kem ranh gioi tu."""
    c, t = cau.lower(), ten.lower()
    i = c.find(t)
    while i != -1:
        truoc = c[i - 1] if i else ""
        sau = c[i + len(t)] if i + len(t) < len(c) else ""
        if not (truoc.isalpha() or DAU_VI.match(truoc or " ")) and \
           not (sau.isalpha() or DAU_VI.match(sau or " ")):
            return True
        i = c.find(t, i + 1)
    return False


def ngu_canh(ten, v, sums, toi_da=2):
    out = []
    hoa = hoa_ten(ten)
    for c, _ in sorted(v["c"], key=lambda x: -x[1]):
        s = sums.get(str(c))
        if not s:
            continue
        for cau in re.split(r"(?<=[.!?…])\s+", s):
            if chua_ten(cau, hoa):
                out.append(f"c.{c}: {cau.strip()[:200]}")
                break
        if len(out) >= toi_da:
            break
    return out


def dung_prompt(nhom, sums, idx):
    phan = []
    for ten in nhom:
        v = idx[ten]
        cc = ngu_canh(ten, v, sums)
        phan.append(f"### {hoa_ten(ten)}\n"
                    f"xuất hiện c.{v['f']}–c.{v['l']}, {v['n']} lần nhắc\n"
                    + ("\n".join(cc) if cc else "(không có câu ví dụ)"))
    bang = "\n".join(f"- {k}: {m}" for k, m in LOAI.items())
    return (f"""/no_think
Phân loại các thực thể sau trong tiểu thuyết tiên hiệp "Vạn Cổ Thần Đế".

NHÃN HỢP LỆ
{bang}

QUY TẮC
- Mỗi thực thể một dòng, đúng định dạng: TÊN | nhãn
- Dùng đúng tên như đã cho, và đúng một nhãn trong danh sách trên.
- Không đủ căn cứ thì ghi nhãn khac. Không giải thích, không thêm gì khác.

THỰC THỂ
""" + "\n\n".join(phan) + "\n\nTRẢ LỜI:")


def hoi(base, model, headers, prompt, retries=4):
    url = base.rstrip("/") + "/v1/chat/completions"
    last = None
    for lan in range(retries):
        body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1, "max_tokens": [2500, 5000, 9000][min(lan, 2)]}
        try:
            j = http_json(url, body, headers)
            m = j["choices"][0]["message"]
            txt = (m.get("content") or "").strip()
            txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
            if txt:
                return txt
            last = f"rỗng (finish_reason={j['choices'][0].get('finish_reason')})"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(min(45, 5 * (2 ** lan)) + random.random())
    raise RuntimeError(last)


def doc_tra_loi(txt, nhom):
    """Chi nhan dong khop voi ten DA HOI va nhan HOP LE."""
    tra = {hoa_ten(t).lower(): t for t in nhom}
    ra = {}
    for line in txt.splitlines():
        if "|" not in line:
            continue
        ten, _, nhan = line.rpartition("|")
        ten = ten.strip().lstrip("-*# ").strip()
        nhan = nhan.strip().lower().replace("-", "_")
        goc = tra.get(ten.lower())
        if goc and nhan in LOAI:
            ra[goc] = nhan
    return ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE", "http://localhost:8000"))
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "qwen3.8"))
    ap.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", ""))
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-mentions", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    headers = {"Authorization": f"Bearer {a.api_key}"} if a.api_key else {}

    with gzip.open(DATA / "index.json.gz", "rt", encoding="utf-8") as f:
        idx = json.load(f)

    if a.apply:
        return ap_dung(idx)

    sums = json.load(gzip.open(DATA / "summaries.json.gz", "rt", encoding="utf-8"))
    xong = set()
    if CKPT.exists():
        for l in CKPT.read_text(encoding="utf-8").splitlines():
            try: xong.add(json.loads(l)["t"])
            except Exception: pass
        print(f"checkpoint: đã có {len(xong)} thực thể")

    can = [t for t, v in idx.items()
           if v["k"] == "khac" and v["n"] >= a.min_mentions and t not in xong]
    can.sort(key=lambda t: -idx[t]["n"])
    if a.limit:
        can = can[:a.limit]
    lo = [can[i:i + LO] for i in range(0, len(can), LO)]
    print(f"cần phân loại: {len(can):,} thực thể · {len(lo)} lượt gọi · model {a.model}\n")
    if not can:
        print("không còn gì để làm."); return

    ck = CKPT.open("a", encoding="utf-8")

    def lam(nhom):
        try:
            txt = hoi(a.base_url, a.model, headers, dung_prompt(nhom, sums, idx))
            ra = doc_tra_loi(txt, nhom)
            with lock:
                for t, k in ra.items():
                    ck.write(json.dumps({"t": t, "k": k}, ensure_ascii=False) + "\n")
                ck.flush()
                dem["ok"] += len(ra)
                thieu = len(nhom) - len(ra)
                if thieu:
                    dem["loi"] += thieu
        except Exception as e:
            if len(nhom) > 1:
                # Chia doi roi lam lai: prompt ngan hon thi model nghi it hon.
                giua = len(nhom) // 2
                lam(nhom[:giua]); lam(nhom[giua:])
                return
            with lock:
                dem["loi"] += len(nhom)
                with LOI.open("a", encoding="utf-8") as lf:
                    lf.write(json.dumps({"nhom": nhom, "err": str(e)[:300]}, ensure_ascii=False) + "\n")
                print(f"  ✗ {nhom[0]}: {e}", file=sys.stderr)
        with lock:
            k = dem["ok"] + dem["loi"]
            if k % 50 < LO:
                el = time.time() - dem["t0"]
                print(f"  {k}/{len(can)} · {k/el*60:.0f} mục/phút · lỗi {dem['loi']}", flush=True)

    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(lam, lo))
    ck.close()
    print(f"\n✓ {dem['ok']} phân loại · {dem['loi']} thiếu/lỗi")
    print("Chạy  python3 pipeline/phan_loai_ai.py --apply  để ghi vào index.json.gz")


def ap_dung(idx):
    if not CKPT.exists():
        sys.exit("chưa có kết quả, chạy không kèm --apply trước.")
    kq = {}
    for l in CKPT.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(l); kq[r["t"]] = r["k"]
        except Exception: pass
    doi = {t: k for t, k in kq.items()
           if t in idx and idx[t]["k"] == "khac" and k != "khac"}
    for t, k in doi.items():
        idx[t]["k"] = k
    with gzip.open(DATA / "index.json.gz", "wt", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))
    NHAN = {"nhan_vat":"Nhân vật","the_luc":"Thế lực","dia_danh":"Địa danh",
            "cong_phap":"Công pháp","bao_vat":"Bảo vật","canh_gioi":"Cảnh giới","khac":"Khác"}
    (DATA / "kind-ai.json").write_text(json.dumps(
        {t: NHAN[k] for t, k in sorted(doi.items())}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ chuyển {len(doi):,} thực thể khỏi nhóm Khác")
    print("  ", dict(Counter(NHAN[k] for k in doi.values()).most_common()))
    print("theo loại:", dict(Counter(NHAN[v["k"]] for v in idx.values()).most_common()))


if __name__ == "__main__":
    main()
