#!/usr/bin/env python3
"""Hiệu đính bản tóm tắt chương (web/data/summaries.json.gz) bằng cùng quy tắc với nội dung chương:
chữ Hán sót -> âm Hán-Việt (chọn theo bigram toàn truyện), rồi bảng sửa tên/chính tả toàn truyện
và bảng sửa theo chương (name-overrides.json, chinh-ta.json).
  python3 pipeline/sua_tom_tat.py"""
import json, gzip, glob, sys
from collections import Counter, defaultdict
from pathlib import Path
APP = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(APP / 'pipeline'))
import hieu_dinh as H
chuong = {}
for f in sorted(glob.glob(str(APP / 'web/data/shard-*.json.gz'))):
    for k, v in json.load(gzip.open(f, 'rt')).items(): chuong[int(k)] = v
uni, bi, hoa = H.dem_ngram(chuong); del chuong
ch = H.ChuHan(uni, bi, hoa); rules = H.nap_bang_sua(); tc = H.nap_theo_chuong()
f = APP / 'web/data/summaries.json.gz'; s = json.load(gzip.open(f, 'rt'))
dem = Counter(); bc = defaultdict(list); doi = 0
for k, v in s.items():
    if not isinstance(v, str): continue
    n = int(k); d = Counter(); m = v
    if H.HAN.search(m): m = ch.sua(m, d, n, bc)
    m = H.ap_theo_chuong(H.ap_bang_sua(m, rules, d), n, tc, d)
    if m != v: s[k] = m; doi += 1
    dem.update(d)
json.dump(s, gzip.open(f, 'wt'), ensure_ascii=False, separators=(',', ':'))
print('tom tat doi', doi, dict(dem)); print('\n'.join(bc['chu_han'][:25]))
