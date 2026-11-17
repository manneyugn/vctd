#!/usr/bin/env python3
"""Buoc 3: mot luot quet corpus -> toan bo chi muc tra cuu.

Xuat ra web/data/:
  index.json.gz   thuc the -> {loai, chuong dau/cuoi, postings [chuong, so lan]}
  cooc.json.gz    thuc the -> cac thuc the hay di cung
  quotes.json.gz  thuc the -> cau trich dan tieu bieu
"""
import gzip, json, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "app" / "web" / "data"

TOP_COOC = 1800        # chi tinh dong xuat hien cho N thuc the noi bat nhat
COOC_KEEP = 12         # giu bao nhieu lien ket moi thuc the
QUOTES_PER = 3
MAXLEN = 4

SPLIT_RE = re.compile(r"[^0-9A-Za-zÀ-ỹ]+")
SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")

# dong tu chi hanh dong cua NGUOI -> tin hieu phan loai nhan vat
PERSON_VERBS = set("""
nói cười hỏi đáp quát gầm hét thở nhìn liếc gật lắc bước đi đứng ngồi
trầm vung giơ nắm buông thu phất rút vỗ chắp cúi ngẩng quay xoay
nghĩ tưởng biết hiểu cảm nhớ quên lo sợ giận mừng
tu luyện thi triển vận chuyển thu hồi xuất thủ động thủ ra tay
ánh mắt gương mặt thân hình trong lòng trên tay
""".split())
PLACE_PREPS = set("tại ở đến về tới rời trong ngoài khắp quanh giữa vào".split())

KIND_LABEL = {
    "nhan_vat": "Nhân vật", "the_luc": "Thế lực", "dia_danh": "Địa danh",
    "cong_phap": "Công pháp", "bao_vat": "Bảo vật", "canh_gioi": "Cảnh giới",
    "khac": "Khác",
}


def load_entities():
    with gzip.open(DATA / "entities.json.gz", "rt", encoding="utf-8") as f:
        ents = json.load(f)["entities"]
    lookup = {}            # ten hoac bi danh -> ten chinh
    for e in ents:
        lookup[e["name"]] = e["name"]
        for a in e["aliases"]:
            lookup[a] = e["name"]
    return ents, lookup


def iter_chapters():
    meta = json.loads((DATA / "chapters.json").read_text(encoding="utf-8"))
    cache = {}
    for ch in meta["chapters"]:
        sid = ch["s"]
        if sid not in cache:
            cache.clear()
            with gzip.open(DATA / f"shard-{sid:03d}.json.gz", "rt", encoding="utf-8") as f:
                cache[sid] = json.load(f)
        yield ch["n"], ch["t"], cache[sid][str(ch["n"])]


def main():
    ents, lookup = load_entities()
    keys = set(lookup)
    by_len = {n: {k for k in keys if k.count(" ") == n - 1} for n in range(2, MAXLEN + 1)}

    postings = defaultdict(Counter)       # ten chinh -> Counter{chuong: so lan}
    ctx_person = Counter()
    ctx_place = Counter()
    quotes = defaultdict(list)
    chapter_sets = {}

    print("quet corpus...", flush=True)
    for num, title, paras in iter_chapters():
        present = set()
        for para in paras:
            for sent in SENT_SPLIT.split(para):
                raw = [t for t in SPLIT_RE.split(sent) if t]
                if len(raw) < 2:
                    continue
                low = [t.lower() for t in raw]
                i, L = 0, len(low)
                while i < L:
                    hit = None
                    for n in range(MAXLEN, 1, -1):          # khop dai nhat truoc
                        if i + n > L:
                            continue
                        g = " ".join(low[i:i + n])
                        if g in by_len.get(n, ()):
                            hit = (g, n)
                            break
                    if hit is None:
                        i += 1
                        continue
                    g, n = hit
                    canon = lookup[g]
                    postings[canon][num] += 1
                    present.add(canon)
                    nxt = low[i + n] if i + n < L else ""
                    prv = low[i - 1] if i > 0 else ""
                    if nxt in PERSON_VERBS:
                        ctx_person[canon] += 1
                    if prv in PLACE_PREPS:
                        ctx_place[canon] += 1
                    if len(quotes[canon]) < QUOTES_PER and 40 <= len(sent) <= 220:
                        quotes[canon].append({"n": num, "t": sent.strip()})
                    i += n
        chapter_sets[num] = present
        if num % 500 == 0:
            print(f"  ...chuong {num}", flush=True)

    # --- phan loai lai bang ngu canh ---
    for e in ents:
        name = e["name"]
        tot = max(sum(postings[name].values()), 1)
        p_ratio = ctx_person[name] / tot
        l_ratio = ctx_place[name] / tot
        if e["kind"] in ("khac", "nhan_vat"):
            if p_ratio >= 0.015 and p_ratio > l_ratio:
                e["kind"] = "nhan_vat"
            elif l_ratio >= 0.05 and l_ratio > p_ratio * 2:
                e["kind"] = "dia_danh"
            elif e["kind"] == "nhan_vat" and p_ratio < 0.004:
                e["kind"] = "khac"

    # --- dong xuat hien ---
    rank = sorted(ents, key=lambda e: -sum(postings[e["name"]].values()))
    hot = {e["name"] for e in rank[:TOP_COOC]}
    pair = Counter()
    for num, present in chapter_sets.items():
        sel = sorted(present & hot)
        for a_i, a in enumerate(sel):
            for b in sel[a_i + 1:]:
                pair[(a, b)] += 1
    cooc = defaultdict(list)
    for (a, b), c in pair.items():
        cooc[a].append((c, b))
        cooc[b].append((c, a))
    cooc = {k: [n for _, n in sorted(v, reverse=True)[:COOC_KEEP]] for k, v in cooc.items()}

    # --- ghi file ---
    index = {}
    for e in ents:
        name = e["name"]
        post = postings[name]
        if not post:
            continue
        chs = sorted(post.items())
        index[name] = {
            "k": e["kind"],
            "a": e["aliases"],
            "f": chs[0][0],
            "l": chs[-1][0],
            "n": sum(post.values()),
            "c": [[c, k] for c, k in chs],
        }

    def dump(obj, fn):
        with gzip.open(DATA / fn, "wt", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  {fn:<20} {(DATA / fn).stat().st_size / 1024:,.0f} KB")

    dump(index, "index.json.gz")
    dump(cooc, "cooc.json.gz")
    dump({k: v for k, v in quotes.items() if v}, "quotes.json.gz")

    kinds = Counter(v["k"] for v in index.values())
    print(f"\nthuc the co postings: {len(index):,}")
    print("theo loai:", {KIND_LABEL[k]: v for k, v in kinds.most_common()})
    print("\ntop 15:")
    for e in rank[:15]:
        v = index.get(e["name"])
        if v:
            print(f"  {v['n']:>7}  c.{v['f']}-{v['l']:<5} {KIND_LABEL[v['k']]:<10} {e['name']}")

if __name__ == "__main__":
    main()
