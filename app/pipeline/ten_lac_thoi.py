#!/usr/bin/env python3
"""Dò tên 'lạc thời': tên riêng xuất hiện ở chương nằm xa vùng xuất hiện chính
(trước khi nhân vật ra mắt), không có ở các chương lân cận -> nghi LLM thay nhầm tên.
Gợi ý tên thay: tên cùng loại có ở chương ±3 nhưng vắng/ít ở chương này.
  python3 pipeline/ten_lac_thoi.py  -> hieu-dinh/ten-lac-thoi.json
"""
import gzip, json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import ten_theo_chuong as T
HD = T.HD
d = json.load(gzip.open(HD/'ten-theo-chuong.json.gz', 'rt')); K = d['_k']
ch = {int(n): c for n, c in d['chuong'].items()}
idx = json.load(gzip.open(T.D/'index.json.gz', 'rt'))
def loai(x): return K.get(x.lower())
out = []
for key, e in idx.items():
    if e['k'] not in ('nhan_vat', 'cong_phap', 'bao_vat') or e['n'] < 40: continue
    cs = dict((a, b) for a, b in e['c'])
    N = sorted(cs)
    # ra mắt dày: chương đầu tiên m mà tên có ở >=3 chương trong [m, m+20]
    debut = next((m for m in N if sum(1 for x in N if m <= x <= m+20) >= 3), N[0])
    for n in N:
        if n >= debut - 30: break
        if any(x in cs for x in range(n-5, n+6) if x != n): continue
        ten = next((k for k in ch[n] if k.lower() == key), key)
        lan = Counter()
        for m in range(n-3, n+4):
            if m != n and m in ch:
                for k, v in ch[m].items():
                    if loai(k) == e['k'] and k.lower() != key: lan[k] += v
        goi_y = [(k, v, ch[n].get(k, 0)) for k, v in lan.most_common(40) if ch[n].get(k, 0) <= cs[n] // 3][:4]
        out.append(dict(n=n, ten=ten, k=e['k'], sl=cs[n], debut=debut, tong=e['n'], goi_y=goi_y))
json.dump(out, open(HD/'ten-lac-thoi.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('ung vien', len(out))
