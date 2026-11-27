#!/usr/bin/env python3
"""Bo loi tac gia, quang cao, rac giao dien trang nguon khoi van truyen.

Quy tac: hieu-dinh/loi-tac-gia.json (ap tren doan DA xu ly, sau dich lai).
  python3 loi_tac_gia.py      -> ap thang vao web/data (shard, chapters.json, summaries, quotes)
build_corpus.py goi ap(noi_dung) truoc khi ghi shard.
"""
import gzip, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = HERE / "hieu-dinh" / "loi-tac-gia.json"
DATA = HERE.parent / "web" / "data"


def nap():
    return json.loads(CFG.read_text(encoding="utf-8"))


def _dau_cham(p):
    return p.strip() in ("...", "…", "……")


def don_chuong(n, ps, R, rac=None):
    rac = rac or [re.compile(x) for x in R.get("rac_dong", [])]
    n = str(n)
    if int(n) in R.get("ca_chuong", []):
        return [R["ghi_chu_ca_chuong"]]
    out = list(ps)
    moc = R.get("cat_cuoi", {}).get(n)
    if moc:
        k = next((i for i, p in enumerate(out) if p.startswith(moc)), None)
        if k is not None:
            out = out[:k]
            while out and _dau_cham(out[-1]):
                out.pop()
    xs = R.get("xoa", {}).get(n, [])
    if xs:
        moi = []
        for i, p in enumerate(out):
            if any(p.startswith(x) for x in xs):
                continue
            moi.append(p)
        out = moi
        # dong '...' mo dau con sot lai sau khi bo ghi chu dau chuong
        while out and _dau_cham(out[0]):
            out.pop(0)
    for a, b in R.get("thay_chuoi", []):
        out = [re.sub(a, b, p) for p in out]
    # rac trang nguon; "Vạn Cổ Thần Đế" ngay truoc "Chưa có tên nào" cung la rac
    moi = []
    for i, p in enumerate(out):
        s = p.strip()
        if any(r.search(s) for r in rac):
            continue
        if s == "Vạn Cổ Thần Đế" and i + 1 < len(out) and out[i + 1].strip() == "Chưa có tên nào":
            continue
        moi.append(p)
    return moi


def ap(noi_dung):
    R = nap()
    rac = [re.compile(x) for x in R.get("rac_dong", [])]
    bo = 0
    for n in list(noi_dung):
        moi = don_chuong(n, noi_dung[n], R, rac)
        bo += len(noi_dung[n]) - len(moi)
        noi_dung[n] = moi
    return bo


def main():
    R = nap()
    rac = [re.compile(x) for x in R.get("rac_dong", [])]
    meta_p = DATA / "chapters.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    byn = {c["n"]: c for c in meta["chapters"]}
    con = {}
    doi_n = set()
    tong = 0
    for f in sorted(DATA.glob("shard-*.json.gz")):
        d = json.load(gzip.open(f, "rt", encoding="utf-8"))
        doi = False
        for n, ps in d.items():
            moi = don_chuong(n, ps, R, rac)
            if moi != ps:
                doi_n.add(int(n))
                tong += len(ps) - len(moi)
                d[n] = moi
                doi = True
                c = byn[int(n)]
                c["p"] = len(moi)
                c["w"] = sum(p.count(" ") + 1 for p in moi)
            con[int(n)] = "\n".join(d[n])
        if doi:
            with gzip.open(f, "wt", encoding="utf-8") as g:
                json.dump(d, g, ensure_ascii=False, separators=(",", ":"))
    meta["totalWords"] = sum(c["w"] for c in meta["chapters"])
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # tom tat chuong chi co loi tac gia
    sp = DATA / "summaries.json.gz"
    s = json.load(gzip.open(sp, "rt", encoding="utf-8"))
    for n in R.get("ca_chuong", []):
        if str(n) in s:
            s[str(n)] = R["ghi_chu_ca_chuong"]
    with gzip.open(sp, "wt", encoding="utf-8") as g:
        json.dump(s, g, ensure_ascii=False, separators=(",", ":"))
    # trich dan tro toi doan da bo
    qp = DATA / "quotes.json.gz"
    q = json.load(gzip.open(qp, "rt", encoding="utf-8"))
    bq = 0
    for k, v in q.items():
        giu = [x for x in v if x["t"].strip('"“” ')[:30] in con.get(x["n"], "") or x["n"] not in doi_n]
        bq += len(v) - len(giu)
        q[k] = giu
    with gzip.open(qp, "wt", encoding="utf-8") as g:
        json.dump(q, g, ensure_ascii=False, separators=(",", ":"))
    print(f"bo {tong} doan, {bq} trich dan")


if __name__ == "__main__":
    main()
