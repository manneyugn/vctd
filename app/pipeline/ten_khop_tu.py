#!/usr/bin/env python3
"""Dò cụm lạ theo từ chung: cụm X hiếm (<=3 chương), không trên wiki, không có ở chương ±5,
chia >=1 từ 'đặc trưng' (không phải từ chung kiểu Thiên/Thần/Đại) với tên C hay xuất hiện ở ±5 chương,
độ dài tùy ý. Ưu tiên cặp chung nhiều từ và X chứa từ thuần Việt.
  python3 pipeline/ten_khop_tu.py -> hieu-dinh/ten-khop-tu.json
"""
import json, gzip, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import ten_theo_chuong as T
HD = T.HD
K = json.load(gzip.open(HD/'ten-theo-chuong.json.gz', 'rt'))['_k']
wiki = json.load(open(HD/'wiki-doi-chieu.json', encoding='utf-8'))['wiki']
WIKI = {e['chuan'] for e in wiki.values() if e['chuan']}
HV = {x for v in json.load(open(HD/'han-viet.json', encoding='utf-8')).values() for x in v}
day = {n: T.cum(ps) for n, ps in T.doc()}
so_ch = Counter(); tu = Counter()
for c in day.values():
    so_ch.update(c.keys())
    for k in c:
        if len(k.split()) == 1: pass
    tu.update(w for k in c for w in set(k.split()))
CHUNG = {w for w, v in tu.most_common(120)}          # từ quá phổ biến trong tên
out = []
for n in sorted(day):
    lan = Counter(); xa = set()
    for m in range(n - 5, n + 6):
        if m != n and m in day:
            xa |= set(day[m])
            for k, v in day[m].items():
                if (K.get(k.lower()) in ('nhan_vat', 'cong_phap', 'bao_vat', 'the_luc', 'dia_danh') or k in WIKI) and len(k.split()) >= 2: lan[k] += v
    for X, cx in day[n].items():
        xs = X.split()
        if len(xs) < 2 or so_ch[X] > 3 or X in WIKI or X in xa: continue
        if any(len(Y) > len(X) and (' ' + X + ' ') in (' ' + Y + ' ') and v >= cx for Y, v in day[n].items()): continue
        dac = set(xs) - CHUNG
        if not dac: continue
        tv = any(w.lower() not in HV for w in xs)
        best = []
        for C, v in lan.items():
            if v < 3 or C == X or C in X or X in C: continue
            chung = dac & set(C.split())
            if chung: best.append((len(chung), v, C))
        if best:
            best.sort(reverse=True)
            out.append(dict(n=n, ten=X, sl=cx, thuan_viet=tv, goi_y=[(c, k, v) for k, v, c in best[:3]]))
json.dump(out, open(HD/'ten-khop-tu.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('ung vien', len(out), '| co tu thuan Viet', sum(r['thuan_viet'] for r in out))
