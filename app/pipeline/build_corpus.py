#!/usr/bin/env python3
"""Buoc 1: doc 4211 chuong tho -> lam sach -> shard gzip cho web app.

Xuat ra web/data/:
  chapters.json        metadata moi chuong (num, title, shard, words)
  shard-XXX.json.gz    noi dung chuong theo lo
  clean-log.json       nhat ky hieu dinh (so loi da sua moi loai, moi chuong)
  hieu-dinh-bao-cao.json  nhung gi hieu dinh tu quyet + nhung gi can nguoi duyet

Hai tang lam sach:
  1. clean()          tung chuong: khoang trang, dau cau, link rac
  2. hieu_dinh.xu_ly  ca truyen: chu Han sot, ten sai chinh ta, viet hoa... (xem hieu_dinh.py)
     Can entities.json.gz tu lan chay truoc de biet ten rieng nao can viet hoa;
     lan dau chua co thi bo qua buoc viet hoa ten (chay lai sau extract_entities).

  python3 pipeline/build_corpus.py              # day du
  python3 pipeline/build_corpus.py --tho        # bo qua hieu dinh (de so sanh)
"""
import gzip, io, json, os, re, sys, time, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hieu_dinh
import loi_tac_gia

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "output" / "van-co-than-de-xtruyen"
OUT = ROOT / "app" / "web" / "data"
SHARD_SIZE = 100

# --- cac quy tac lam sach (moi quy tac dem rieng de bao cao) ---
RULES = []

def rule(name):
    def deco(fn):
        RULES.append((name, fn))
        return fn
    return deco

@rule("quote_spacing")
def _quote_spacing(t):
    n = 0
    # chu"trich dan"chu  ->  chu "trich dan" chu
    t, k = re.subn(r'(?<=[^\s"])"(?=[^\s"])', '" ', t); n += k
    t, k = re.subn(r'(?<=[\wÀ-ỹ])"(?=\s)', '"', t); n += 0
    # mo ngoac dinh lien tu truoc
    t, k = re.subn(r'(\S)"(\S)', r'\1" \2', t); n += k
    return t, n

@rule("punct_spacing")
def _punct_spacing(t):
    n = 0
    t, k = re.subn(r'\s+([,.;:!?])', r'\1', t); n += k          # khoang trang truoc dau cau
    t, k = re.subn(r'([,;:])(?=[^\s\d])', r'\1 ', t); n += k     # thieu khoang sau dau phay
    return t, n

@rule("ellipsis")
def _ellipsis(t):
    t, k = re.subn(r'\.{4,}', '...', t)
    return t, k

@rule("junk_links")
def _junk(t):
    n = 0
    for pat in (r'https?://\S+', r'www\.\S+\.\w{2,}',
                r'(?i)nguon\s*:\s*\S+', r'(?i)truyen\s*cv\s*\S*',
                r'(?i)doc truyen tai\s*\S+'):
        t, k = re.subn(pat, '', t); n += k
    return t, n

@rule("whitespace")
def _ws(t):
    n = 0
    t, k = re.subn(r'[ \t]{2,}', ' ', t); n += k
    t, k = re.subn(r'\n{3,}', '\n\n', t); n += k
    return t.strip(), n

def clean(text):
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    counts = {}
    for name, fn in RULES:
        text, k = fn(text)
        if k:
            counts[name] = counts.get(name, 0) + k
    return text, counts

DICH_LAI = Path(__file__).resolve().parent / "hieu-dinh" / "dich-lai"

def ap_dich_lai(noi_dung):
    """Ap ban dich lai cac doan phien am tho (hieu-dinh/dich-lai/<n>.done.json).
    Moi doan: {idx: {goc, dich}}; dich rong => bo doan. Khop theo chi so, lech thi tim theo van ban goc."""
    sua = lech = 0
    for f in sorted(DICH_LAI.glob("*.done.json")):
        num = int(f.name.split(".", 1)[0])
        paras = noi_dung.get(num)
        if paras is None:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        moi = list(paras)
        for k, d in data["doan"].items():
            i = int(k)
            if i < len(paras) and paras[i] == d["goc"]:
                j = i
            elif d["goc"] in paras:
                j = paras.index(d["goc"])
            elif len(paras) == data.get("so_doan") and i < len(paras):
                j = i
            else:
                lech += 1
                continue
            moi[j] = d["dich"]
            sua += 1
        noi_dung[num] = [x for x in moi if x and x.strip()]
    return sua, lech

def main():
    manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    files = {}
    for p in (SRC / "chapters").iterdir():
        if p.suffix == ".txt":
            try:
                files[int(p.name.split("_", 1)[0])] = p
            except ValueError:
                pass

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # tang 1: lam sach tung chuong
    entries, noi_dung, dem_1, missing = [], {}, {}, []
    for entry in sorted(manifest["chapters"], key=lambda c: c["num"]):
        num = entry["num"]
        path = files.get(num)
        if path is None:
            missing.append(num)
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        text, counts = clean(raw)
        entries.append(entry)
        noi_dung[num] = [p.strip() for p in text.split("\n\n") if p.strip()]
        dem_1[num] = counts
    print(f"lam sach    : {len(entries)} chuong  ({time.time() - t0:.0f}s)")

    # tang 2: hieu dinh ca truyen
    dem_2, bao_cao = {}, {}
    if "--tho" not in sys.argv:
        ent_path = OUT / "entities.json.gz"
        entities = []
        if ent_path.exists():
            with gzip.open(ent_path, "rt", encoding="utf-8") as f:
                entities = json.load(f)["entities"]
        else:
            print("  ! chua co entities.json.gz -> bo qua viet hoa ten rieng")
        noi_dung, dem_2, bao_cao = hieu_dinh.xu_ly(noi_dung, entities)
        tieu_de, k = hieu_dinh.sua_tieu_de({e["num"]: e.get("title", f"Chuong {e['num']}") for e in entries})
        for e in entries:
            e["title"] = tieu_de[e["num"]]
        print(f"tieu de     : sua {k}")
        print(f"hieu dinh   : xong  ({time.time() - t0:.0f}s)")
        sua, lech = ap_dich_lai(noi_dung)
        print(f"dich lai    : {sua} doan  (khong khop: {lech})")
        print(f"loi tac gia : bo {loi_tac_gia.ap(noi_dung)} doan")

    for old in OUT.glob("shard-*.json.gz"):
        old.unlink()
    chapters, log, shard, shard_id = [], [], {}, 0
    total_words = 0

    for entry in entries:
        num = entry["num"]
        paras = noi_dung[num]
        counts = dict(dem_1[num])
        for k, v in dem_2.get(num, {}).items():
            counts[k] = counts.get(k, 0) + v
        words = sum(p.count(" ") + 1 for p in paras)
        total_words += words

        sid = (len(chapters)) // SHARD_SIZE
        if sid != shard_id and shard:
            _flush(shard, shard_id)
            shard, shard_id = {}, sid
        shard[str(num)] = paras

        chapters.append({
            "n": num,
            "t": entry.get("title", f"Chuong {num}").strip(),
            "s": sid,
            "w": words,
            "p": len(paras),
        })
        if counts:
            log.append({"n": num, "fixes": counts})

    if shard:
        _flush(shard, shard_id)

    (OUT / "chapters.json").write_text(json.dumps({
        "title": manifest["book"]["title"],
        "author": manifest["book"]["author"],
        "source": manifest.get("domain", ""),
        "shardSize": SHARD_SIZE,
        "totalWords": total_words,
        "chapters": chapters,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    totals = {}
    for row in log:
        for k, v in row["fixes"].items():
            totals[k] = totals.get(k, 0) + v
    with gzip.open(OUT / "clean-log.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"totals": totals, "chapters": log}, f, ensure_ascii=False, separators=(",", ":"))

    if bao_cao:
        (OUT / "hieu-dinh-bao-cao.json").write_text(
            json.dumps(bao_cao, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"chuong      : {len(chapters)}  (thieu: {missing or 'khong'})")
    print(f"tong tu     : {total_words:,}")
    print(f"shard       : {shard_id + 1}")
    print(f"loi da sua  : {sum(totals.values()):,} -> {totals}")

def _flush(shard, sid):
    with gzip.open(OUT / f"shard-{sid:03d}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(shard, f, ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__":
    main()
