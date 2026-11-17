#!/usr/bin/env python3
"""Sau build_index.py: chep lai LOAI va BO LOC tu mot index cu.

build_index.py dung index tu entities.json.gz nen mat het nhung gi phan_loai.py,
phan_loai_ai.py --apply va buoc loc manh vun da lam tren index cu. Khi chi doi
NGUYEN VAN (vd sau hieu dinh) ma khong doi danh sach thuc the, chay script nay
de giu nguyen cong phan loai, chi lay postings / dong xuat hien / trich dan moi.

  cp web/data/index.json.gz /tmp/index-cu.json.gz     # truoc khi build_index
  python3 pipeline/build_index.py
  python3 pipeline/giu_phan_loai.py /tmp/index-cu.json.gz
"""
import gzip, json, sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "web" / "data"


def doc(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def ghi(p, obj):
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def loc_ten(x, giu):
    """Bo moi tham chieu toi thuc the da bi loc, du cau truc long the nao."""
    if isinstance(x, dict):
        return {k: loc_ten(v, giu) for k, v in x.items() if not (isinstance(k, str) and k in BO)}
    if isinstance(x, list):
        out = []
        for v in x:
            if isinstance(v, str) and v in BO:
                continue
            if isinstance(v, list) and v and isinstance(v[0], str) and v[0] in BO:
                continue
            if isinstance(v, dict) and any(isinstance(v.get(k), str) and v[k] in BO for k in ("t", "name", "e")):
                continue
            out.append(loc_ten(v, giu))
        return out
    return x


def main():
    cu = doc(sys.argv[1])
    moi = doc(DATA / "index.json.gz")
    global BO
    BO = {t for t in moi if t not in cu}
    doi = 0
    for t, v in moi.items():
        if t in cu and v.get("k") != cu[t].get("k"):
            v["k"] = cu[t]["k"]
            doi += 1
    giu = {t: v for t, v in moi.items() if t in cu}
    ghi(DATA / "index.json.gz", giu)
    for ten in ("cooc.json.gz", "quotes.json.gz"):
        p = DATA / ten
        if p.exists():
            ghi(p, loc_ten(doc(p), giu))
    thieu = [t for t in cu if t not in moi]
    print(f"index moi  : {len(moi):,} -> giu {len(giu):,} (bo {len(BO):,} muc da loc truoc day)")
    print(f"loai       : chep lai {doi:,} muc tu index cu")
    if thieu:
        print(f"  ! {len(thieu)} muc co o index cu nhung khong con: {thieu[:10]}")


if __name__ == "__main__":
    main()
