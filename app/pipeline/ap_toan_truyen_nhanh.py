#!/usr/bin/env python3
"""Áp nhanh cặp sửa tên toàn truyện đã duyệt (chỉ khớp đúng cụm viết hoa, nguyên từ):
ghi vào chinh-ta.json mục ten_dich_nghia (để lần build sau vẫn giữ) rồi sửa thẳng shard /
summaries / quotes / chapters.json / dich-lai.
  python3 pipeline/ap_toan_truyen_nhanh.py cap.json "ghi chú"     cap.json: {"sai": "dung", ...}
  cap.json có thể có khoá "_regex": {pattern: thay}  -> ghi vào mục regex."""
import json, gzip, glob, re, sys
from pathlib import Path
APP = Path(__file__).resolve().parent.parent; P = APP / 'pipeline'; D = APP / 'web/data'
CHU = 'A-Za-zÀ-ỹĐđ'
cap = json.load(open(sys.argv[1], encoding='utf-8')); rx_moi = cap.pop('_regex', {})
f = P / 'hieu-dinh/chinh-ta.json'; c = json.load(open(f, encoding='utf-8'))
c['ten_dich_nghia'].update(cap); c['regex'].update(rx_moi)
if len(sys.argv) > 2: c['_doc'].append(sys.argv[2])
open(f, 'w', encoding='utf-8').write(json.dumps(c, ensure_ascii=False, indent=2) + '\n')
R = [(re.compile(rf'(?<![{CHU}]){re.escape(k)}(?![{CHU}])'), v) for k, v in sorted(cap.items(), key=lambda x: -len(x[0]))]
R += [(re.compile(k), v) for k, v in rx_moi.items()]
dem = [0]
def sub(s):
    for r, v in R:
        s, k = r.subn(v, s); dem[0] += k
    return s
def walk(o):
    if isinstance(o, str): return sub(o)
    if isinstance(o, list): return [walk(x) for x in o]
    if isinstance(o, dict): return {k: walk(v) for k, v in o.items()}
    return o
for fn in sorted(glob.glob(str(D / 'shard-*.json.gz'))) + [str(D / 'summaries.json.gz'), str(D / 'quotes.json.gz')]:
    d = json.load(gzip.open(fn, 'rt')); m = walk(d)
    if m != d: json.dump(m, gzip.open(fn, 'wt'), ensure_ascii=False, separators=(',', ':'))
fn = D / 'chapters.json'; d = json.load(open(fn, encoding='utf-8')); m = walk(d)
if m != d: open(fn, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, separators=(',', ':')))
for fn in glob.glob(str(P / 'hieu-dinh/dich-lai/*.done.json')):
    d = json.load(open(fn, encoding='utf-8')); m = walk(d)
    if m != d: open(fn, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=0))
print('cap', len(R), 'thay', dem[0])
