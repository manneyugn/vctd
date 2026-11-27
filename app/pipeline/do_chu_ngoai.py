#!/usr/bin/env python3
"""Dò từ không phải tiếng Việt trong nội dung chương + tóm tắt: chữ ngoài bảng chữ Việt (Hindi, Hàn,
Nhật, Cyrillic, Latin có dấu lạ...), hoặc từ Latin không thể là âm tiết tiếng Việt (có f/j/w/z,
phụ âm cuối lạ, cụm phụ âm đầu lạ) — thường là tiếng Anh/pinyin LLM để sót.
  python3 pipeline/do_chu_ngoai.py -> hieu-dinh/chu-ngoai.json"""
import json, gzip, glob, re, unicodedata as U
from collections import Counter, defaultdict
from pathlib import Path
APP = Path(__file__).resolve().parent.parent
VIET = set('aăâbcdđeêghiklmnoôơpqrstuưvxy')
DAU = '̣̀́̃̉'
def goc(w):
    w = U.normalize('NFD', w.lower()); return U.normalize('NFC', ''.join(c for c in w if c not in DAU))
DAU_AM = r'(?:ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|[bcdđghklmnpqrstvx])?'
VAN = r'[aăâeêioôơuưy]{1,3}(?:ng|nh|ch|[cmnpt])?'
AM = re.compile(rf'^{DAU_AM}{VAN}$')
TU = re.compile(r"[^\W\d_]+", re.U)
c = Counter(); ch = defaultdict(set); vd = {}
def quet(s, n):
    for m in TU.finditer(s):
        w = m.group(); g = goc(w)
        la = any(not ('a' <= x <= 'z' or x in 'đăâêôơư') for x in g) or not AM.match(g)
        if la and len(w) > 1:
            c[w] += 1; ch[w].add(n)
            vd.setdefault(w, f'{n}: …{s[max(0, m.start()-50):m.end()+30]}…')
for f in sorted(glob.glob(str(APP / 'web/data/shard-*.json.gz'))):
    for k, v in json.load(gzip.open(f, 'rt')).items():
        for p in v: quet(p, int(k))
for k, v in json.load(gzip.open(APP / 'web/data/summaries.json.gz', 'rt')).items():
    if isinstance(v, str): quet(v, 't' + k)
out = [dict(tu=w, lan=n, chuong=sorted(ch[w], key=str)[:20], vd=vd[w]) for w, n in c.most_common()]
json.dump(out, open(APP / 'pipeline/hieu-dinh/chu-ngoai.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('tu', len(out), 'lan', sum(c.values()))
