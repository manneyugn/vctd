#!/usr/bin/env python3
"""Dò tên bị dịch nghĩa (kiểu 韩湫 -> "Hàn Thấp Trũng Hồ Nước"): nhân vật C xuất hiện dày ở các
chương ±3 nhưng vắng hẳn ở chương n; trong chương n có cụm viết hoa bắt đầu bằng họ (âm tiết đầu)
của C, khác C, không có ở chương lân cận -> nghi là C bị dịch nghĩa / viết sai độ dài.
  python3 pipeline/ten_dich_nghia.py -> hieu-dinh/ten-dich-nghia.json
"""
import json, gzip, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import ten_theo_chuong as T
HD = T.HD
K = json.load(gzip.open(HD/'ten-theo-chuong.json.gz', 'rt'))['_k']
wiki = json.load(open(HD/'wiki-doi-chieu.json', encoding='utf-8'))['wiki']
WIKI = {e['chuan'] for e in wiki.values() if e['chuan']}
day = {n: T.cum(ps) for n, ps in T.doc()}
HV = {x for v in json.load(open(HD/'han-viet.json', encoding='utf-8')).values() for x in v}
def thuan_viet(x): return any(w.lower() not in HV for w in x.split()[1:])
tong = Counter()
for c in day.values(): tong.update(c)
out = []
for n in sorted(day):
    lan = Counter(); so = Counter()
    for m in range(n - 3, n + 4):
        if m != n and m in day:
            for k, v in day[m].items():
                if (K.get(k.lower()) == 'nhan_vat' or k in WIKI) and len(k.split()) >= 2: lan[k] += v; so[k] += 1
    xa = set()
    for m in range(n - 5, n + 6):
        if m != n and m in day: xa |= set(day[m])
    for C, v in lan.items():
        if v < 6 or so[C] < 2 or day[n].get(C, 0) > 0: continue
        ho = C.split()[0]
        cand = [(X, cx) for X, cx in day[n].items()
                if X.split()[0] == ho and len(X.split()) > len(C.split()) and thuan_viet(X) and X not in xa and tong[X] <= 60
                and not any(len(Y) > len(X) and Y.startswith(X + ' ') and day[n][Y] >= cx for Y in day[n])]
        if cand: out.append(dict(n=n, ten=C, lan=v, cum=sorted(cand, key=lambda x: -x[1])[:4]))
json.dump(out, open(HD/'ten-dich-nghia.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('ung vien', len(out))
