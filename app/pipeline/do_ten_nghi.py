#!/usr/bin/env python3
"""Dò tên/thuật ngữ nghi sai, không dựa vào danh sách từ khoá có sẵn:
  (A) am_la   : cụm viết hoa giữa câu có âm tiết KHÔNG phải âm Hán-Việt (han-viet.json)
                -> nghi bị dịch nghĩa ("Tịnh Mệt Thần Hỏa", "Trương Rốt Trần", "Nửa Thánh").
  (B) the_cho : nhân vật C có mặt dày ở chương n-1 và n+1 nhưng VẮNG ở chương n, trong khi chương n
                có cụm X không hề xuất hiện ở n±5 -> nghi C bị đổi tên cả chương ("Trương Vô Cực" c933).
Cụm đã duyệt là đúng ghi vào hieu-dinh/ten-nghi-bo-qua.txt (mỗi dòng một cụm) để lần sau không báo lại.
  python3 pipeline/do_ten_nghi.py -> hieu-dinh/ten-nghi.json
"""
import json, gzip, glob, re, unicodedata as U
from collections import Counter, defaultdict
from pathlib import Path
APP = Path(__file__).resolve().parent.parent; HD = APP / 'pipeline' / 'hieu-dinh'
DAU = '̣̀́̃̉'
def chuan(w):  # so khớp không phụ thuộc kiểu bỏ dấu (thủy/thuỷ)
    w = U.normalize('NFD', w.lower())
    return U.normalize('NFC', ''.join(c for c in w if c not in DAU)) + '|' + ''.join(c for c in w if c in DAU)
HV = {chuan(x) for v in json.load(open(HD / 'han-viet.json', encoding='utf-8')).values() for x in v}
BO = set()
f = HD / 'ten-nghi-bo-qua.txt'
if f.exists(): BO = {l.strip() for l in open(f, encoding='utf-8') if l.strip() and not l.startswith('#')}
UP = 'A-ZĐÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ'
LO = 'a-zà-ỹđ'
CAP = re.compile(rf'(?:[{UP}][{LO}]* ){{1,4}}[{UP}][{LO}]*')
GIUA = re.compile(rf'(?<=[{LO},] )(?:[{UP}][{LO}]* ){{1,4}}[{UP}][{LO}]*')   # giữa câu: tránh chữ hoa đầu câu

day, giua, vd = {}, defaultdict(Counter), {}
for fn in sorted(glob.glob(str(APP / 'web/data/shard-*.json.gz'))):
    for k, ps in json.load(gzip.open(fn, 'rt')).items():
        n = int(k); s = '\n'.join(ps)
        day[n] = Counter(CAP.findall(s))
        for m in GIUA.finditer(s):
            giua[m.group()][n] += 1
            vd.setdefault(m.group(), f'c{n}: …{s[max(0, m.start()-60):m.end()+40]}…'.replace('\n', ' '))
tong = Counter()
for c in day.values(): tong.update(c)
# bản tóm tắt chương cũng quét (A): ghi chương dạng "t<n>"
for k, s in json.load(gzip.open(APP / 'web/data/summaries.json.gz', 'rt')).items():
    if not isinstance(s, str): continue
    for m in GIUA.finditer(s):
        giua[m.group()]['t' + k] += 1
        vd.setdefault(m.group(), f't{k}: …{s[max(0, m.start()-60):m.end()+40]}…')

# (A)
am_la = []
for X, ch in giua.items():
    ws = X.split(); la = [w for w in ws if chuan(w) not in HV]
    if not la or len(la) == len(ws) or X in BO: continue
    # gợi ý: tên thường gặp cùng độ dài, trùng mọi âm tiết Hán-Việt của X
    am_la.append(dict(cum=X, lan=sum(ch.values()), chuong=sorted(ch, key=str), am_la=la, vd=vd[X]))
am_la.sort(key=lambda x: -x['lan'])

# (B)
K = json.load(gzip.open(HD / 'ten-theo-chuong.json.gz', 'rt'))['_k']
the_cho = []
for n in sorted(day):
    if n - 1 not in day or n + 1 not in day: continue
    xa = set()
    for m in range(n - 5, n + 6):
        if m != n and m in day: xa |= set(day[m])
    for C in set(day[n - 1]) & set(day[n + 1]):
        a, b = day[n - 1][C], day[n + 1][C]
        if len(C.split()) < 2 or min(a, b) < 8 or day[n].get(C) or K.get(C.lower()) != 'nhan_vat': continue
        cand = [(X, v) for X, v in day[n].most_common(40) if X not in xa and v >= 5 and len(X.split()) >= 2 and X not in BO]
        if cand: the_cho.append(dict(chuong=n, vang=C, truoc=a, sau=b, the=cand[:3]))
json.dump(dict(am_la=am_la, the_cho=the_cho), open(HD / 'ten-nghi.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('am_la', len(am_la), 'lan', sum(x['lan'] for x in am_la), '| the_cho', len(the_cho))
