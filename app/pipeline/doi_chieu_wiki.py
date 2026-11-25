#!/usr/bin/env python3
"""Đối chiếu ứng viên tên lẫn (ten-lan.json) với danh mục tên lấy từ wiki (hieu-dinh/wiki-ten.txt).
Tên wiki (chữ Hán) -> mọi cách đọc Hán-Việt -> cách đọc có trong truyện nhiều nhất = tên chuẩn.
  python3 pipeline/doi_chieu_wiki.py -> hieu-dinh/wiki-doi-chieu.json
"""
import json, gzip, itertools, re, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import ten_theo_chuong as T
HD = T.HD; HV = json.load(open(HD/'han-viet.json', encoding='utf-8'))
ten = [w for l in open(HD/'wiki-ten.txt', encoding='utf-8') if not l.startswith('#') for w in l.split()]
ten = list(dict.fromkeys(ten))
d = json.load(gzip.open(HD/'ten-theo-chuong.json.gz', 'rt'))['chuong']
tong = Counter()
for c in d.values(): tong.update(c)
def doc(w):
    opts = [HV.get(ch) for ch in w]
    if any(o is None for o in opts): return []
    out = []
    for combo in itertools.islice(itertools.product(*opts), 4096):
        out.append(' '.join(x.capitalize() for x in combo))
    return out
wiki = {}; bien = {}   # bien: cách đọc HV -> tên Hán
for w in ten:
    vs = doc(w)
    if not vs: continue
    co = sorted(((tong.get(v, 0), v) for v in vs), reverse=True)
    wiki[w] = dict(chuan=co[0][1] if co[0][0] else None, sl=co[0][0], khac=[(v, n) for n, v in co[1:] if n])
    for v in vs: bien[v] = w
print('ten wiki', len(wiki), 'co trong truyen', sum(1 for x in wiki.values() if x['chuan']))
L = json.load(open(HD/'ten-lan.json', encoding='utf-8'))
cap = defaultdict(lambda: dict(sl=0, ch=[]))
for r in L:
    k = (r['sai'], r['dung']); cap[k]['sl'] += r['sl']; cap[k]['ch'].append(r['n'])
def thuoc(x):   # x có nằm trong (hoặc chính là) cách đọc của tên wiki nào
    if x in bien: return bien[x], True
    return None, None
ket = []
for (V, C), e in cap.items():
    wv, dv = thuoc(V); wc, dc = thuoc(C)
    if wv and wv != wc: kl = 'giu'      # biến thể chính là/thuộc 1 tên wiki khác -> tên thật, không sửa
    elif wc and not wv: kl = 'sua'      # tên chuẩn có trên wiki, biến thể thì không
    else: continue
    ket.append(dict(sai=V, dung=C, kl=kl, wiki_dung=wc, wiki_sai=wv, sl=e['sl'], ch=sorted(e['ch'])))
# thêm: cách đọc Hán-Việt khác của cùng tên wiki đang dùng trong truyện -> đổi về cách đọc phổ biến
for w, e in wiki.items():
    for v, n in e['khac']:
        if e['chuan'] and n < e['sl']: ket.append(dict(sai=v, dung=e['chuan'], kl='doc_khac', wiki_dung=w, sl=n, ch=None))
json.dump(dict(wiki=wiki, ket=ket), open(HD/'wiki-doi-chieu.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(Counter(r['kl'] for r in ket))
