#!/usr/bin/env python3
"""Dò 'tên lạ': tên riêng chỉ xuất hiện lẻ loi (ít chương), không có trên wiki, không có ở
chương ±W, nhưng gần giống (theo từng âm tiết) một nhân vật đang xuất hiện ở các chương lân cận.
  python3 pipeline/ten_la.py [W] -> hieu-dinh/ten-la.json
"""
import json, gzip, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import ten_theo_chuong as T
W = int(sys.argv[1]) if len(sys.argv) > 1 else 5
HD = T.HD
d = json.load(gzip.open(HD/'ten-theo-chuong.json.gz', 'rt')); K = d['_k']
ch = {int(n): c for n, c in d['chuong'].items()}
# đếm đầy đủ từ văn bản (kể cả cụm chỉ xuất hiện 1 lần) để bắt tên sai lẻ
day = {n: T.cum(ps) for n, ps in T.doc()}
HV = {x for v in json.load(open(HD/'han-viet.json', encoding='utf-8')).values() for x in v}
wiki = json.load(open(HD/'wiki-doi-chieu.json', encoding='utf-8'))['wiki']
WIKI = {e['chuan'] for e in wiki.values() if e['chuan']} | {v for e in wiki.values() for v, _ in e['khac']}
so_ch = Counter(); tong = Counter()
for c in day.values(): so_ch.update(c.keys()); tong.update(c)
NV = {'nhan_vat'}
def la_hv(x): return all(s.lower() in HV for s in x.split())
def giong(a, b):
    A, B = a.split(), b.split()
    if len(A) != len(B) or a == b: return 0
    sc = [3 if x == y else T.gan(x, y) for x, y in zip(A, B)]
    if 0 in sc: return 0
    khac = sum(1 for s in sc if s < 3)
    if khac > max(1, len(A) // 2): return 0
    return sum(sc) / (3 * len(A))
out = []
for n in sorted(ch):
    lan = Counter()
    for m in range(n - W, n + W + 1):
        if m in ch:
            for k, v in ch[m].items():
                if K.get(k.lower()) in NV or k in WIKI: lan[k] += v
    for X, cx in day[n].items():
        if so_ch[X] > 3 or X in WIKI or not la_hv(X) or len(X.split()) < 2: continue
        if any(X in day.get(m, {}) for m in range(n - W, n + W + 1) if m != n): continue
        # bỏ cụm con: X luôn nằm trong một cụm dài hơn của chính chương này
        if any(len(Y) > len(X) and (' '+X+' ') in (' '+Y+' ') and v >= cx for Y, v in day[n].items()): continue
        # bỏ cụm mà từ đầu là chữ đầu câu kiểu thường (Nếu, Trong...): từ đầu phải là âm Hán-Việt hay dùng trong tên
        best = sorted(((giong(X, C), lan[C], C) for C in lan if lan[C] >= 3), reverse=True)
        best = [b for b in best if b[0] > 0][:3]
        if best: out.append(dict(n=n, ten=X, sl=cx, so_ch=so_ch[X], goi_y=[(c, round(s, 2), v) for s, v, c in best]))
json.dump(out, open(HD/'ten-la.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('ten la', len(out), '| sl>=2:', sum(1 for r in out if r['sl'] >= 2))
