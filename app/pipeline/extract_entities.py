#!/usr/bin/env python3
"""Buoc 2: tim ten rieng trong ban convert (ten khong viet hoa nhat quan).

Khong dung AI. Ket hop 3 tin hieu:
  1. do ket dinh n-gram  (cohesion / PMI)  - "con lon" luon di voi nhau
  2. ty le viet hoa giua cau               - convert van hoa mot phan ten rieng
  3. mau ngu canh Han-Viet                 - ...giới, ...tông, ...đế, ...quân

Xuat: web/data/entities.json.gz
"""
import gzip, json, math, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "app" / "web" / "data"

MIN_COUNT = {2: 25, 3: 12, 4: 8}
MAX_N = 4
TOP_KEEP = 20000

# Tu chuc nang / tu pho thong: ten rieng gan nhu khong bao gio chua chung
STOP = set("""
va cung voi cua cho den tu tai trong ngoai tren duoi truoc sau giua khi luc
la co khong chua da dang se vua moi con mat bi duoc phai nen the nay no
mot hai ba bon nam sau bay tam chin muoi tram ngan van ty cai chiec con nguoi
ta nguoi hang nang han chung minh toi ban ho no y gi sao vay nhu nhung nhieu it
rat qua lam hon nhat cuc het ca moi tung deu chi cung ngay cang van lai
ma thi nhung nhung_ con_ neu thi_ do boi vi nen_ nhung ro rang dang le
ra vao len xuong di den ve lai dung ngoi nam dung_ noi rang nghe thay nhin
biet hieu nghi tuong cam thay muon can phai nen_ co_the khong_the
trong_luc sau_do truoc_do bay_gio hien_tai luc_nay khi_do ngay_cang
than the nay kia ay do day dau sao the_nao nhu_vay nhu_the boi_vi
lan tiếng tieng chut phan ben phia huong mat long tay chan dau mieng
""".split())

VI_COMMON = set("""
của và với cho đến từ tại trong ngoài trên dưới trước sau giữa khi lúc
là có không chưa đã đang sẽ vừa mới còn mất bị được phải nên thế này nọ
một hai ba bốn năm sáu bảy tám chín mười trăm nghìn vạn tỷ cái chiếc con người
ta ngươi hắn nàng chúng mình tôi bạn họ nó ý gì sao vậy như những nhiều ít
rất quá lắm hơn nhất cực hết cả mọi từng đều chỉ càng ngày vẫn lại
mà thì nếu đó bởi vì ra vào lên xuống đi về dừng đứng ngồi nằm nói rằng
nghe thấy nhìn biết hiểu nghĩ tưởng cảm muốn cần thân thể nay kia ấy đây đâu
lần tiếng chút phần bên phía hướng mặt lòng tay chân đầu miệng mắt
trận đạo khí lực tâm thần ý pháp công thế lên cũng liền đem tới đối
sự việc người vị cái lúc nơi chỗ chuyện điều cách lối phía bọn
rồi xong nữa hề luôn ngay thật rõ hẳn chừng độ khoảng chừng_như
""".split())

CTX_SUFFIX = {
    "giới": "dia_danh", "thành": "dia_danh", "sơn": "dia_danh", "cốc": "dia_danh",
    "vực": "dia_danh", "trạch": "dia_danh", "quốc": "dia_danh", "châu": "dia_danh",
    "cung": "dia_danh", "điện": "dia_danh", "lâu": "dia_danh", "động": "dia_danh",
    "uyên": "dia_danh", "hải": "dia_danh", "nguyên": "dia_danh", "đảo": "dia_danh",
    "tông": "the_luc", "môn": "the_luc", "phái": "the_luc", "cung_điện": "the_luc",
    "gia": "the_luc", "tộc": "the_luc", "viện": "the_luc", "hội": "the_luc",
    "các": "the_luc", "đường": "the_luc", "bang": "the_luc", "quân": "the_luc",
    "quyết": "cong_phap", "pháp": "cong_phap", "kinh": "cong_phap", "thuật": "cong_phap",
    "chỉ": "cong_phap", "chưởng": "cong_phap", "quyền": "cong_phap", "kiếm_pháp": "cong_phap",
    "ấn": "cong_phap", "điển": "cong_phap", "công": "cong_phap",
    "kiếm": "bao_vat", "đao": "bao_vat", "thương": "bao_vat", "giáp": "bao_vat",
    "đỉnh": "bao_vat", "tháp": "bao_vat", "châu": "bao_vat", "đan": "bao_vat",
    "bội": "bao_vat", "kính": "bao_vat", "chung": "bao_vat", "phù": "bao_vat",
    "cảnh": "canh_gioi", "kỳ": "canh_gioi", "tầng": "canh_gioi", "trùng": "canh_gioi",
    "đế": "nhan_vat", "tôn": "nhan_vat", "vương": "nhan_vat", "hoàng": "nhan_vat",
    "tử": "nhan_vat", "nữ": "nhan_vat", "lão": "nhan_vat", "chủ": "nhan_vat",
    "sư": "nhan_vat", "tiên": "nhan_vat", "thần": "nhan_vat", "ma": "nhan_vat",
}

SPLIT_RE = re.compile(r"[^0-9A-Za-zÀ-ỹ]+")
SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n")


def iter_chapters():
    meta = json.loads((DATA / "chapters.json").read_text(encoding="utf-8"))
    cache = {}
    for ch in meta["chapters"]:
        sid = ch["s"]
        if sid not in cache:
            cache.clear()
            with gzip.open(DATA / f"shard-{sid:03d}.json.gz", "rt", encoding="utf-8") as f:
                cache[sid] = json.load(f)
        yield ch["n"], cache[sid][str(ch["n"])]


def main():
    uni = Counter()
    ngrams = {n: Counter() for n in range(2, MAX_N + 1)}
    cap_hits = Counter()      # n-gram xuat hien voi am tiet viet hoa (giua cau)
    total_tokens = 0

    print("pass 1: dem n-gram...", flush=True)
    for num, paras in iter_chapters():
        for para in paras:
            for sent in SENT_SPLIT.split(para):
                raw = [t for t in SPLIT_RE.split(sent) if t]
                if not raw:
                    continue
                low = [t.lower() for t in raw]
                total_tokens += len(low)
                uni.update(low)
                for n in range(2, MAX_N + 1):
                    for i in range(len(low) - n + 1):
                        if any(w in VI_COMMON or w in STOP for w in low[i:i + n]):
                            continue
                        g = " ".join(low[i:i + n])
                        ngrams[n][g] += 1
                        # viet hoa giua cau = tin hieu ten rieng
                        if i > 0 and sum(1 for w in raw[i:i + n] if w[:1].isupper()) >= max(1, n - 1):
                            cap_hits[g] += 1
        if num % 500 == 0:
            print(f"  ...chuong {num}", flush=True)
            for n in ngrams:
                if len(ngrams[n]) > 4_000_000:
                    ngrams[n] = Counter({k: v for k, v in ngrams[n].items() if v >= 3})

    print(f"  tokens: {total_tokens:,}  unigram: {len(uni):,}", flush=True)

    print("pass 2: cham diem...", flush=True)
    N = float(total_tokens)
    scored = []
    for n in range(2, MAX_N + 1):
        counts = ngrams[n]
        floor = MIN_COUNT[n]
        for g, c in counts.items():
            if c < floor:
                continue
            parts = g.split(" ")
            # do ket dinh: so voi lan cat yeu nhat
            best = 0.0
            for k in range(1, n):
                left = " ".join(parts[:k]); right = " ".join(parts[k:])
                lc = uni[left] if k == 1 else ngrams[k].get(left, 0)
                rc = uni[right] if n - k == 1 else ngrams[n - k].get(right, 0)
                if lc <= 0 or rc <= 0:
                    best = 0.0
                    break
                pmi = math.log((c / N) / ((lc / N) * (rc / N)) + 1e-12)
                best = pmi if best == 0.0 else min(best, pmi)
            if best <= 2.0:
                continue
            cap = cap_hits.get(g, 0) / c
            # nguong quyet dinh: ten rieng trong ban convert gan nhu luon duoc
            # viet hoa giua cau (0.68-0.96); cum tu thong dung nam o 0.00-0.08
            if cap < 0.30:
                continue
            score = math.log(c) * best * (1.0 + 2.5 * cap)
            scored.append((score, g, c, round(cap, 3), n))

    scored.sort(reverse=True)
    scored = scored[:TOP_KEEP]
    print(f"  ung vien: {len(scored):,}", flush=True)

    # gan loai theo am tiet cuoi / dau
    out = []
    for score, g, c, cap, n in scored:
        parts = g.split(" ")
        kind = CTX_SUFFIX.get(parts[-1], "")
        if not kind and parts[0] in ("thần", "tiên", "ma", "yêu", "long"):
            kind = "khac"
        out.append({
            "name": g, "count": c, "cap": cap, "n": n,
            "score": round(score, 2), "kind": kind or "khac",
        })

    with gzip.open(DATA / "entities-raw.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"tokens": total_tokens, "entities": out}, f, ensure_ascii=False, separators=(",", ":"))

    by_kind = Counter(e["kind"] for e in out)
    print(f"da luu {len(out)} thuc the -> entities-raw.json.gz")
    print("theo loai:", dict(by_kind))
    print("\ntop 30:")
    for e in out[:30]:
        print(f"  {e['count']:>6}  cap={e['cap']:.2f}  {e['kind']:<10} {e['name']}")

if __name__ == "__main__":
    main()
