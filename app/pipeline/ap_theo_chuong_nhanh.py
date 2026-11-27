#!/usr/bin/env python3
"""Áp nhanh các cặp sửa theo chương đã duyệt, không cần chạy lại build_corpus:
ghi vào name-overrides.json (mục theo_chuong, để lần build sau vẫn giữ) rồi sửa thẳng
shard / summaries / quotes / chapters.json / dich-lai của đúng các chương đó.
  python3 pipeline/ap_theo_chuong_nhanh.py dot.json "ghi chú"
  dot.json: [{"sai": "...", "dung": "...", "chuong": [n, ...]}, ...]
Sau đó chạy bước 2 của pipeline (build_index ... build_public)."""
import json, gzip, re, sys
from collections import defaultdict
from pathlib import Path
APP = Path(__file__).resolve().parent.parent; P = APP / 'pipeline'; D = APP / 'web/data'
CHU = 'A-Za-zÀ-ỹĐđ'
dot = json.load(open(sys.argv[1], encoding='utf-8')); ghi = sys.argv[2] if len(sys.argv) > 2 else ''
ovr = json.load(open(P / 'name-overrides.json', encoding='utf-8'))
co = {(r['sai'], r['dung']): r for r in ovr['theo_chuong']}
for e in dot:
    r = co.get((e['sai'], e['dung']))
    if r: r['chuong'] = sorted(set(r['chuong']) | set(e['chuong']))
    else:
        r = dict(sai=e['sai'], dung=e['dung'], chuong=sorted(e['chuong']), ghi_chu=ghi); ovr['theo_chuong'].append(r); co[(e['sai'], e['dung'])] = r
open(P / 'name-overrides.json', 'w', encoding='utf-8').write(json.dumps(ovr, ensure_ascii=False, indent=2) + '\n')
tc = defaultdict(list)
for e in dot:
    rx = re.compile(rf"(?<![{CHU}])(?<!Đại )(?<!Quỷ ){re.escape(e['sai'])}(?![{CHU}])")
    for c in e['chuong']: tc[int(c)].append((rx, e['dung']))
dem = [0]
def sua(s, n):
    for rx, d in tc.get(int(n), ()):
        s, k = rx.subn(d, s); dem[0] += k
    return s
for sh in sorted({(n - 1) // 100 for n in tc}):
    f = D / f'shard-{sh:03d}.json.gz'; d = json.load(gzip.open(f, 'rt'))
    for k in d:
        if int(k) in tc: d[k] = [sua(p, k) for p in d[k]]
    json.dump(d, gzip.open(f, 'wt'), ensure_ascii=False, separators=(',', ':'))
n_shard = dem[0]
f = D / 'summaries.json.gz'; d = json.load(gzip.open(f, 'rt'))
for k in d:
    if k.isdigit() and int(k) in tc: d[k] = sua(d[k], k) if isinstance(d[k], str) else json.loads(sua(json.dumps(d[k], ensure_ascii=False), k))
json.dump(d, gzip.open(f, 'wt'), ensure_ascii=False, separators=(',', ':'))
f = D / 'quotes.json.gz'; d = json.load(gzip.open(f, 'rt'))
for v in d.values():
    for q in v:
        if isinstance(q, dict) and q.get('n') in tc: q['t'] = sua(q['t'], q['n'])
json.dump(d, gzip.open(f, 'wt'), ensure_ascii=False, separators=(',', ':'))
f = D / 'chapters.json'; d = json.load(open(f, encoding='utf-8'))
for c in d['chapters']:
    if c['n'] in tc: c['t'] = sua(c['t'], c['n'])
open(f, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, separators=(',', ':')))
for n in tc:
    f = P / 'hieu-dinh/dich-lai' / f'{n}.done.json'
    if f.exists():
        d = json.load(open(f, encoding='utf-8'))
        for v in d['doan'].values(): v['dich'] = sua(v['dich'], n)
        open(f, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=0))
print('cap', len(dot), 'chuong', len(tc), 'thay trong shard', n_shard, 'tong', dem[0])
