#!/usr/bin/env python3
"""Index tên riêng theo từng chương + dò tên bị lẫn giữa các chương lân cận.

  python3 pipeline/ten_theo_chuong.py index     # -> hieu-dinh/ten-theo-chuong.json.gz
  python3 pipeline/ten_theo_chuong.py do [W]    # -> hieu-dinh/ten-lan.json (ứng viên)

Tên = cụm 2-5 âm tiết viết hoa liên tiếp. Ứng viên lẫn: biến thể V ở chương n
khác tên chuẩn C đúng một âm tiết (âm tiết "gần giống"), C xuất hiện nhiều ở
các chương ±W nhưng vắng ở chương n, và V hiếm trong cửa sổ đó.
"""
import gzip, json, glob, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; D = ROOT/'web'/'data'; HD = Path(__file__).resolve().parent/'hieu-dinh'
TOK = re.compile(r"[^\W\d_]+|[^\w\s]", re.U)
def hoa(w): return w[:1].isupper()
def doc():
    for f in sorted(glob.glob(str(D/'shard-*.json.gz'))):
        for n, ps in json.load(gzip.open(f, 'rt')).items(): yield int(n), ps
def cum(ps):
    c = Counter()
    for p in ps:
        for cau in re.split(r'[.!?…:"“”\n]', p):
            run = []
            for t in TOK.findall(cau) + ['.']:
                if t.isalpha() and hoa(t): run.append(t); continue
                if len(run) >= 2:
                    for i in range(len(run)):
                        for L in range(2, 6):
                            if i + L <= len(run): c[' '.join(run[i:i+L])] += 1
                run = []
    return c
def bo_dau(s):
    s = s.lower().replace('đ', 'd')
    return ''.join(ch for ch in unicodedata.normalize('NFD', s) if not unicodedata.combining(ch))
def lev(a, b):
    p = list(range(len(b)+1))
    for i, x in enumerate(a, 1):
        q = [i]
        for j, y in enumerate(b, 1): q.append(min(p[j]+1, q[j-1]+1, p[j-1]+(x != y)))
        p = q
    return p[-1]
def gan(a, b):
    A, B = bo_dau(a), bo_dau(b)
    if A == B: return 3
    d = lev(A, B)
    if d == 1: return 2
    if d == 2 and (A[0] == B[0] or A[-2:] == B[-2:]) and min(len(A), len(B)) >= 3: return 1
    return 0
def index():
    idx = json.load(gzip.open(D/'index.json.gz', 'rt'))
    out = {}
    for n, ps in doc():
        c = cum(ps)
        out[n] = {k: v for k, v in c.items() if v >= 2 or k.lower() in idx}
    with gzip.open(HD/'ten-theo-chuong.json.gz', 'wt', encoding='utf-8') as g:
        json.dump({'_k': {k: v['k'] for k, v in idx.items()}, 'chuong': out}, g, ensure_ascii=False, separators=(',', ':'))
    print('chuong', len(out), 'ten/chuong tb', sum(map(len, out.values()))//len(out))
def do(W=12):
    # dùng counter đầy đủ (kể cả tên xuất hiện 1 lần) để bắt biến thể lẻ
    ch = {n: cum(ps) for n, ps in doc()}
    tong = Counter(); so_ch = Counter()
    for c in ch.values(): tong.update(c); so_ch.update(c.keys())
    # khoá wildcard -> tên chuẩn tiềm năng (tổng >= 20)
    khoa = defaultdict(list)
    for k, v in tong.items():
        if v >= 20:
            s = k.split()
            for i in range(len(s)): khoa[(len(s), i, tuple(s[:i] + s[i+1:]))].append(k)
    N = sorted(ch); out = []
    for n in N:
        lan = [ch[m] for m in range(n-W, n+W+1) if m != n and m in ch]
        for V, cv in ch[n].items():
            if tong[V] > 300: continue
            s = V.split()
            for i in range(len(s)):
                for C in khoa.get((len(s), i, tuple(s[:i] + s[i+1:])), []):
                    if C == V: continue
                    g = gan(s[i], C.split()[i])
                    if not g: continue
                    cC_n = ch[n].get(C, 0)
                    lanC = sum(x.get(C, 0) for x in lan); lanV = sum(x.get(V, 0) for x in lan)
                    soC = sum(1 for x in lan if C in x)
                    if lanC < 3 or soC < 2 or lanV > lanC/4 or cC_n > cv: continue
                    out.append(dict(n=n, sai=V, dung=C, sl=cv, c_trong=cC_n, lanC=lanC, lanV=lanV, soC=soC,
                                    tongV=tong[V], tongC=tong[C], chV=so_ch[V], gan=g))
    # bỏ ứng viên do cụm con/cha trùng lặp: giữ cụm dài nhất cho cùng (n, vị trí)
    json.dump(out, open(HD/'ten-lan.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('ung vien', len(out), 'cap', len({(o['sai'], o['dung']) for o in out}))
if __name__ == '__main__':
    {'index': index, 'do': lambda: do(int(sys.argv[2]) if len(sys.argv) > 2 else 12)}[sys.argv[1]]()
