#!/usr/bin/env python3
"""Dò tên bị đổi 1 âm tiết bất kỳ (kể cả đổi hẳn họ: Cái Hạo -> Hách Hạo): cụm X hiếm (<=3 chương),
không có ở chương ±5, khác đúng 1 âm tiết với nhân vật C đang xuất hiện ở ±5 chương (>=3 lần),
không đòi hỏi âm tiết khác nhau phải giống nhau.
  python3 pipeline/ten_doi_ho.py -> hieu-dinh/ten-doi-ho.json
"""
import json, gzip, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import ten_theo_chuong as T
HD = T.HD
K = json.load(gzip.open(HD/'ten-theo-chuong.json.gz', 'rt'))['_k']
wiki = json.load(open(HD/'wiki-doi-chieu.json', encoding='utf-8'))['wiki']
WIKI = {e['chuan'] for e in wiki.values() if e['chuan']}
HV = {x for v in json.load(open(HD/'han-viet.json', encoding='utf-8')).values() for x in v}
day = {n: T.cum(ps) for n, ps in T.doc()}
so_ch = Counter()
for c in day.values(): so_ch.update(c.keys())
out = []
for n in sorted(day):
    lan = Counter(); xa = set()
    for m in range(n - 5, n + 6):
        if m != n and m in day:
            xa |= set(day[m])
            for k, v in day[m].items():
                if (K.get(k.lower()) == 'nhan_vat' or k in WIKI) and len(k.split()) >= 2: lan[k] += v
    khoa = defaultdict(list)
    for C, v in lan.items():
        if v < 3: continue
        s = C.split()
        for i in range(len(s)): khoa[(len(s), i, tuple(s[:i] + s[i+1:]))].append(C)
    for X, cx in day[n].items():
        s = X.split()
        if len(s) < 2 or so_ch[X] > 3 or X in WIKI or X in xa: continue
        if not all(w.lower() in HV for w in s): continue
        if any(len(Y) > len(X) and (' ' + X + ' ') in (' ' + Y + ' ') and v >= cx for Y, v in day[n].items()): continue
        for i in range(len(s)):
            for C in khoa.get((len(s), i, tuple(s[:i] + s[i+1:])), []):
                if C != X and day[n].get(C, 0) < cx:
                    out.append(dict(n=n, ten=X, sl=cx, dung=C, lan=lan[C], vt=i, trong=day[n].get(C, 0)))
json.dump(out, open(HD/'ten-doi-ho.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('ung vien', len(out))
