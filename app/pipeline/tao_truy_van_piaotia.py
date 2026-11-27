import json,sys,unicodedata as U,re
sys.path.insert(0,'pipeline')
DAU='̣̀́̃̉'
def chuan(w):
    w=U.normalize('NFD',w.lower()); return U.normalize('NFC',''.join(c for c in w if c not in DAU))+'|'+''.join(c for c in w if c in DAU)
HV=json.load(open('pipeline/hieu-dinh/han-viet.json'))
rev={}
for ch,rs in HV.items():
    if not ('一'<=ch<='鿿'): continue
    for r in rs: rev.setdefault(chuan(r),set()).add(ch)
def cls(w):
    s=rev.get(chuan(w))
    return '['+''.join(sorted(s))+']' if s else '[一-鿿]'
titles={c['n']:c['t'] for c in json.load(open('web/data/chapters.json'))['chapters']}
d=json.load(open('pipeline/hieu-dinh/ten-nghi.json')); SK=set(open('pipeline/hieu-dinh/ten-nghi-chua-ro.txt').read().split('\n')); d['am_la']=[x for x in d['am_la'] if x['cum'] not in SK and not x['cum'].startswith('Ti Xi')]
start=int(sys.argv[1]); k=int(sys.argv[2])
out=[]
for x in d['am_la'][start:start+k]:
    ch=[c for c in x['chuong'] if isinstance(c,int)]
    if not ch: continue
    n=ch[0]; t=titles[n]
    tre=''.join(cls(w) for w in t.split()[:4])
    nre=''.join(cls(w) for w in x['cum'].split())
    out.append([x['cum'],n,tre,nre])
s=json.dumps(out,ensure_ascii=False,separators=(',',':'))
open('/tmp/q.json','w').write(s); print(len(s))
