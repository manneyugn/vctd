#!/usr/bin/env python3
"""Buoc 1: doc 4211 chuong tho -> lam sach -> shard gzip cho web app.

Xuat ra web/data/:
  chapters.json        metadata moi chuong (num, title, shard, words)
  shard-XXX.json.gz    noi dung chuong theo lo
  clean-log.json       nhat ky hieu dinh (so loi da sua moi loai, moi chuong)
"""
import gzip, io, json, os, re, sys, unicodedata
from pathlib import Path

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
    for old in OUT.glob("shard-*.json.gz"):
        old.unlink()

    chapters, log, shard, shard_id, missing = [], [], {}, 0, []
    total_words = 0

    for entry in sorted(manifest["chapters"], key=lambda c: c["num"]):
        num = entry["num"]
        path = files.get(num)
        if path is None:
            missing.append(num)
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        text, counts = clean(raw)
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
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

    print(f"chuong      : {len(chapters)}  (thieu: {missing or 'khong'})")
    print(f"tong tu     : {total_words:,}")
    print(f"shard       : {shard_id + 1}")
    print(f"loi da sua  : {sum(totals.values()):,} -> {totals}")

def _flush(shard, sid):
    with gzip.open(OUT / f"shard-{sid:03d}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(shard, f, ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__":
    main()
