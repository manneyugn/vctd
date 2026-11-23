#!/usr/bin/env python3
"""Hieu dinh nguyen van: chinh ta, chu Han sot, viet hoa. Goi tu build_corpus.py.

Xu ly TOAN BO truyen mot luc (khong phai tung chuong) vi nhieu quyet dinh can
thong ke ca truyen: chon am Han-Viet nao cho chu Han sot, ten rieng nao dang
viet hoa, hau to "giới/tộc" nen viet hoa hay khong.

Thu tu:
  1. dau_cau     「」《》“” -> "  ,  、。，！？ -> dau Viet,  …… -> ...
     + ghi_chu_llm: ghi chu cua LLM dich con sot (ghi_chu_llm.py + hieu-dinh/sua-tay.json)
  2. rac         loi tac gia cuoi chuong (cau phieu...), dong 第123章
  3. chu_han     chu Han sot -> am Han-Viet, chon theo ngu canh (bigram ca truyen)
     + chu_la    chu Thai/Han/Nhat/Kirin/A Rap lot vao giua chu Viet -> tu hop ngu canh
  4. ten_rieng   cap sua da duyet trong name-overrides.json + Han-Viet bi dich nghia
  5. chinh_ta    bang loi chinh ta thong dung (hieu-dinh/chinh-ta.json)
  6. ngoac_kep   ghep cap " de sua khoang trang:  giường" kẽo kẹt" -> giường "kẽo kẹt"
  7. viet_hoa    ten rieng / thuat ngu thong nhat, dau cau, dau loi thoai, doan bi cat
Moi quy tac dem rieng tung chuong -> clean-log (tab Hieu dinh).
Nhung gi khong chac thi ghi vao web/data/hieu-dinh-bao-cao.json de nguoi duyet.
"""
import gzip, itertools, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ghi_chu_llm
CFG = HERE / "hieu-dinh"

HOA = "A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐĨŨƠƯẠẢẤẦẨẬẮẰẲẶẸẺẼẾỀỂỆỈỊỌỎỐỒỔỘỚỜỞỢỤỦỨỪỬỰỲỴỶỸ"
THUONG = "a-zàáâãèéêìíòóôõùúýăđĩũơưạảấầẩậắằẳặẹẻẽếềểệỉịọỏốồổộớờởợụủứừửựỳỵỷỹ"
CHU = HOA + THUONG
TU = re.compile(rf"[{CHU}]+")
NGUYEN_AM = re.compile(r"[aăâeêioôơuưyàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]")
HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]+")
# chu cua bang ma khac lot vao giua chu Viet: Thai, Han Quoc, kana Nhat, Kirin, A Rap
CHU_LA = re.compile(r"[\u0E00-\u0E7F\uAC00-\uD7AF\u1100-\u11FF\u3040-\u30FF\u0400-\u04FF\u0600-\u06FF]+")


def hoa_dau(s):
    return s[:1].upper() + s[1:]


def hoa_ten(s):
    return " ".join(hoa_dau(w) for w in s.split(" "))


def cung_kieu(goc, moi):
    """Giu kieu viet hoa cua chu dau tien (sua 'khoảng khắc' / 'Khoảng khắc')."""
    return hoa_dau(moi) if goc[:1].isupper() else moi


# ---------------------------------------------------------------- 1. dau cau
BANG_DAU = str.maketrans({
    "「": '"', "」": '"', "『": '"', "』": '"', "《": '"', "》": '"', "〈": '"', "〉": '"',
    "“": '"', "”": '"', "„": '"', "‟": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'",
    "。": ".", "，": ",", "、": ",", "！": "!", "？": "?", "：": ":", "；": ";",
    "（": "(", "）": ")", "～": "~", "　": " ", "【": "[", "】": "]",
})


def _cap_ngoac(m, q='"'):
    return " " + q + m.group(1).strip() + q + " "


def dau_cau(p, dem):
    goc = p
    # cap ngoac Trung truoc (giu dung vi tri mo/dong), phan le moi tra bang
    # ten sach/cong phap: trong doan co loi thoai thi dung nhay don de khong long ngoac kep
    co_thoai = bool(re.search(r'["“”「」]', p))
    p = re.sub(r"《\s*([^《》]*?)\s*》", lambda m: _cap_ngoac(m, "'" if co_thoai else '"'), p)
    p = re.sub(r"「\s*([^「」]*?)\s*」", _cap_ngoac, p)
    p = re.sub(r"『\s*([^『』]*?)\s*』", _cap_ngoac, p)
    p = re.sub(r"“\s*([^“”]*?)\s*”", _cap_ngoac, p)
    p = p.translate(BANG_DAU)
    p = re.sub(r"…+", "...", p)
    p = re.sub(r"\.{4,}", "...", p)
    p = re.sub(r"\s+([,.;:!?])", r"\1", p)             # khoang trang truoc dau cau
    p = re.sub(r"([,;])(?=[^\s\d\"')\]])", r"\1 ", p)   # thieu khoang sau dau phay
    p = re.sub(r"(?<=[{0}])\.\.\.(?=[{0}])".format(CHU), "... ", p)
    p = re.sub(r"[ \t]{2,}", " ", p).strip()
    p = re.sub(r"\s+([,.;:!?])", r"\1", p)
    p = re.sub(r"([(\[]) +", r"\1", p)
    p = re.sub(r" +([)\]])", r"\1", p)
    if p != goc:
        dem["dau_cau"] += 1
    return p


# ---------------------------------------------------------------- 2. rac
RAC = re.compile(r"(?i)(cầu phiếu|phiếu đề cử|nguyệt phiếu|phiếu tháng|vé tháng|"
                 r"hoạt động ngoại truyện|gửi ngoại truyện|hòm thư|hộp thư|"
                 r"cập nhật rất chậm|bảo vệ cơ bản|bảo đảm\.\)|cầu đặt mua)")
# loi tac gia (Phi Thien Ngu / "Tieu Ngu") cuoi chuong: lich cap nhat, WeChat, xin loi viet nham...
LOI_TAC_GIA = re.compile(r"(?i)(cập nhật|tiểu ngư|phi thiên ngư|đặt đọc|chương nữa|hai chương|ba chương|"
                         r"bốn ngàn chữ|ngàn chữ|đồng hồ sinh học|lỗi bug|\bbug\b|công chúng hiệu|wechat|"
                         r"microblogging|vi tín|feitianyu|bạn đọc|độc giả|đạo hữu nào|hồng bao|bao lì xì)")
TIEU_DE_HAN = re.compile(r"^\s*(第\s*\d+\s*(章|chương)?|Chương\s*\d+\s*:\s*,?)\s*\S{0,80}$")


def loc_rac(paras, dem, bao_cao, n):
    ra = []
    for i, p in enumerate(paras):
        cuoi = i >= len(paras) - 4
        bo = False
        if RAC.search(p) and (cuoi or (p.startswith("(") and p.rstrip(".").endswith(")"))):
            bo = True
        elif cuoi and LOI_TAC_GIA.search(p) and '"' not in p:
            bo = True
        elif "第" in p and TIEU_DE_HAN.match(p) and len(p) < 90:
            bo = True
        if bo:
            dem["rac"] += 1
            bao_cao["rac"].append(f"c{n}: {p[:120]}")
        else:
            ra.append(p)
    return ra


# ---------------------------------------------------------------- 3. chu Han
class ChuHan:
    def __init__(self, unigram, bigram, hoa):
        self.hv = json.loads((CFG / "han-viet.json").read_text(encoding="utf-8"))
        tay = json.loads((CFG / "tu-han.json").read_text(encoding="utf-8"))
        self.tu, self.chu = tay["tu"], tay["chu"]
        self.uni, self.bi, self.hoa = unigram, bigram, hoa
        self.hoc = {}                       # chu Han -> am, hoc tu chu thich "(...)"
        self.chua_ro = Counter()

    def am_tiet_hop_le(self, w):
        w = w.lower()
        return w not in ("gi", "qu") and bool(NGUYEN_AM.search(w)) and self.uni.get(w, 0) >= 30

    # hoc tu chu thich trong ngoac: "Trương若塵 (Trương Nhược Trần)"
    def hoc_chu_thich(self, p):
        for m in re.finditer(rf"([{CHU}]*)({HAN.pattern})\s*\(([^()]{{1,60}})\)", p):
            run, gl = m.group(2), m.group(3).strip()
            if HAN.search(gl):
                continue
            if not re.fullmatch(rf"[{CHU} ]+", gl):
                continue
            P = gl.lower().split()
            truoc = TU.findall(p[:m.start(2)].lower())[-4:]
            j = self._khop(truoc, P)
            if len(P) - j == len(run):
                self.hoc.setdefault(run, Counter())[" ".join(P[j:])] += 1

    @staticmethod
    def _khop(truoc, P):
        for k in range(min(len(truoc), len(P)), 0, -1):
            if truoc[-k:] == P[:k]:
                return k
        return 0

    def ti_le_hoa(self, w):
        w = w.lower()
        return self.hoa.get(w, 0) / max(1, self.uni.get(w, 0))

    def ung_vien(self, run):
        hoc = [self.hoc[run].most_common(1)[0][0]] if run in self.hoc else []
        return hoc + [c for c in self._tu_dien(run) if c not in hoc]

    def _tu_dien(self, run):
        if run in self.tu:
            return list(self.tu[run])
        # tach tham lam theo tu nhieu chu trong bang tay
        phan, i = [], 0
        while i < len(run):
            for L in range(min(4, len(run) - i), 0, -1):
                k = run[i:i + L]
                if L > 1 and k in self.tu:
                    phan.append(self.tu[k]); i += L; break
                if L == 1:
                    phan.append(self.chu.get(k) or self.hv.get(k) or ["?"]); i += 1
        if any(x == ["?"] for x in phan):
            self.chua_ro[run] += 1
            phan = [[""] if x == ["?"] else x for x in phan]
        # bien the y/i: "hy" ~ "hi", "ly" ~ "li" (ten rieng hay viet kieu i)
        phan = [x + [a[:-1] + "i" for a in x if len(a) > 1 and a.endswith("y") and a[-2] not in "uơ"]
                + [a[:-1] + "y" for a in x if len(a) > 1 and a.endswith("i") and a[-2] not in "aoôơuưe"] for x in phan]
        so = 1
        for x in phan:
            so *= len(x)
        if so > 64:
            phan = [x[:1] for x in phan]
        out = []
        for tohop in itertools.product(*phan):
            s = " ".join(t for t in tohop if t)
            out.append(s)
        return out

    def diem(self, truoc1, cand, sau1):
        w = cand.split()
        if not w:
            return 6 * self.bi.get((truoc1, sau1), 0) + 0.5
        s = 0.0
        if truoc1:
            s += 3 * self.bi.get((truoc1, w[0]), 0)
        for a, b in zip(w, w[1:]):
            s += 2 * self.bi.get((a, b), 0)
        if sau1:
            s += 3 * self.bi.get((w[-1], sau1), 0)
        s += 0.001 * min(self.uni.get(x, 0) for x in w)
        return s

    def sua_chu_la(self, p, dem, n, bao_cao):
        """'chớp lóع' -> 'chớp lóe', 'truyền t송 trận' -> 'truyền tống trận', 'bọnพวก' -> 'bọn họ'."""
        for _ in range(30):
            m = CHU_LA.search(p)
            if not m:
                return p
            s, e = m.span()
            mt = re.search(rf"[{CHU}]*$", p[:s]); mp = re.match(rf"[{CHU}]*", p[e:])
            dau, cuoi = mt.group(), mp.group()
            a, b = s - len(dau), e + len(cuoi)
            truoc = TU.findall(p[:a].lower()[-40:]); sau = TU.findall(p[b:].lower()[:40])
            t1 = truoc[-1] if truoc else ""; s1 = sau[0] if sau else ""
            d0, c0 = dau.lower(), cuoi.lower()
            best, diem = None, -1.0
            if d0 or c0:
                for w, c in self.uni.items():
                    if c < 20 or not w.startswith(d0) or not w.endswith(c0) or len(w) > len(d0) + len(c0) + 4:
                        continue
                    sc = 3 * self.bi.get((t1, w), 0) + 3 * self.bi.get((w, s1), 0) + 0.001 * c
                    if sc > diem:
                        best, diem = w, sc
                # hai tu: "tuوي" -> "tu vi", "tinhこう" -> "tinh không"
                if d0 and not c0 and self.am_tiet_hop_le(d0) and len(d0) >= 2 and self.uni.get(d0, 0) >= 300:
                    theo = sorted(((self.bi[(x, y)], y) for (x, y) in self._sau(d0)), reverse=True)[:30]
                    for c, y in theo:
                        if c < 30:
                            continue
                        sc = 3 * self.bi.get((t1, d0), 0) + 2 * c + 3 * self.bi.get((y, s1), 0)
                        if sc > diem * 1.5:
                            best, diem = d0 + " " + y, sc
            moi = best or (dau + cuoi)
            if dau[:1].isupper():
                moi = hoa_ten(moi) if len(moi.split()) > 1 and cuoi[:1].isupper() else hoa_dau(moi)
            p = p[:a] + moi + p[b:]
            p = re.sub(r" {2,}", " ", p)
            dem["chu_la"] += 1
            if len(bao_cao["chu_la"]) < 300:
                bao_cao["chu_la"].append(f"c{n}: {dau}{m.group()}{cuoi} -> {moi!r}")
        return p

    def _sau(self, x):
        if not hasattr(self, "_idx_sau"):
            self._idx_sau = {}
            for (a, b) in self.bi:
                self._idx_sau.setdefault(a, []).append((a, b))
        return self._idx_sau.get(x, [])

    def sua(self, p, dem, n, bao_cao):
        vong = 0
        while True:
            m = HAN.search(p)
            if not m or vong > 200:
                return p
            vong += 1
            run, s, e = m.group(), m.start(), m.end()
            trai, phai = p[:s], p[e:]

            # manh vun dinh lien truoc: "Trương Nhược Đ尘", "Địa S獄", "Lâm Kh 空"
            ma = re.search(rf"([{CHU}]+)( ?)$", trai)
            dinh = None
            if ma and (ma.group(2) == "" or not self.am_tiet_hop_le(ma.group(1))):
                dinh = ma.group(1)
            vun = dinh is not None and not self.am_tiet_hop_le(dinh)
            if vun:
                trai = trai[:ma.start()]
                dinh_hoa = dinh[:1].isupper()
            # ngoac chu thich ngay sau
            mp = re.match(r"\s*\(([^()]{1,80})\)", phai)
            if mp:
                gl = mp.group(1).strip()
                phai = phai[mp.end():]
                if not HAN.search(gl) and not vun:
                    P = gl.split()
                    tw = list(re.finditer(rf"[{CHU}]+", trai))[-4:]
                    j = self._khop([x.group().lower() for x in tw], [x.lower() for x in P])
                    if len(P) - j == len(run):
                        bat_dau = tw[-j].start() if j else len(trai)
                        cat = trai[:bat_dau]
                        cach = " " if cat and cat[-1].isalnum() else ""
                        p = cat + cach + " ".join(P) + phai
                        dem["chu_han"] += 1
                        continue
            truoc = TU.findall(trai.lower()[-60:])
            sau = TU.findall(phai.lower()[:40])
            t1 = truoc[-1] if truoc else ""
            s1 = sau[0] if sau else ""
            cands = self.ung_vien(run)
            best = max(cands, key=lambda c: (self.diem(t1, c, s1), -cands.index(c)))
            # "tu修为" -> "tu vi": bo am tiet bi lap
            if dinh and not vun and best and best.split()[0] == dinh.lower():
                trai = trai[:len(trai) - len(dinh)]
            # viet hoa
            if best:
                if vun:
                    hoa = dinh_hoa
                elif dinh:
                    # dinh lien la tu thuong ("võ场") -> viet thuong; la ten ("Trương若塵") -> hoa
                    hoa = dinh[:1].isupper() and (giua_cau(trai, len(trai) - len(dinh))
                                                  or self.ti_le_hoa(dinh) >= 0.5 or len(run) >= 2)
                else:
                    tw = list(re.finditer(rf"[{CHU}]+", trai))
                    pw = re.findall(rf"[{CHU}]+", phai[:30])
                    hoa = bool(tw and tw[-1].group()[:1].isupper() and giua_cau(trai, tw[-1].start())) \
                        or bool(pw and pw[0][:1].isupper() and phai[:1] == " ")
                best = hoa_ten(best) if hoa else best
                if not trai.strip() or re.search(r"[.!?\"]\s*$", trai):
                    best = hoa_dau(best)
            cach_t = " " if trai and (trai[-1].isalnum() or trai[-1] in ",;:") and best else ""
            cach_p = " " if phai and phai[0].isalnum() and (best or trai) else ""
            if not best:
                trai = trai.rstrip(" ")
                cach_p = " " if phai and phai[0].isalnum() and trai and trai[-1].isalnum() else ""
            p = trai + cach_t + best + cach_p + phai
            p = re.sub(r" {2,}", " ", p)
            dem["chu_han"] += 1
            if len(bao_cao["chu_han"]) < 400:
                bao_cao["chu_han"].append(f"c{n}: {run} -> {best!r}  …{trai[-25:]}[{best}]{phai[:15]}…")


# ---------------------------------------------------------------- 4-5. ten rieng, chinh ta
def nap_bang_sua():
    rules = []      # (regex, thay_bang, ten_quy_tac, giu_kieu)
    ovr = json.loads((HERE / "name-overrides.json").read_text(encoding="utf-8"))
    for sai, dung in ovr.get("duyet", {}).items():
        rules.append((re.compile(rf"(?<![{CHU}]){re.escape(sai)}(?![{CHU}])", re.I), hoa_ten(dung), "ten_rieng", False))
    # chi khop khi viet hoa kieu ten: "Trì Giao" -> "Trì Dao", nhung "duy trì giao dịch" giu nguyen
    for sai, dung in ovr.get("duyet_viet_hoa", {}).items():
        rules.append((re.compile(rf"(?<![{CHU}]){re.escape(hoa_ten(sai))}(?![{CHU}])"), hoa_ten(dung), "ten_rieng", False))
    ct = json.loads((CFG / "chinh-ta.json").read_text(encoding="utf-8"))
    for sai, dung in ct.get("ten_dich_nghia", {}).items():
        # chi sua khi dang viet hoa nhu ten (tranh 'rút kiếm hai lần')
        rules.append((re.compile(rf"(?<![{CHU}]){re.escape(hoa_ten(sai))}(?![{CHU}])"), hoa_ten(dung), "ten_rieng", False))
    for sai, dung in ct.get("ten_dich_nghia_moi_kieu", {}).items():
        rules.append((re.compile(rf"(?<![{CHU}]){re.escape(sai)}(?![{CHU}])", re.I), hoa_ten(dung), "ten_rieng", False))
    for sai, dung in ct.get("chinh_ta", {}).items():
        rules.append((re.compile(rf"(?<![{CHU}]){re.escape(sai)}(?![{CHU}])", re.I), dung, "chinh_ta", True))
    for pat, dung in ct.get("regex", {}).items():
        rules.append((re.compile(pat), dung, "chinh_ta", None))
    return rules


def nap_theo_chuong():
    """name-overrides.json 'theo_chuong': {chuong: [(regex, ten_dung)]}. LLM dich phien am sai ten
    ca chuong ("Đế Lục" o c607, chuong 606/608 deu la "Đế Nhất"); cung chu o chuong khac co
    the la nghia khac ("Đại Đế Thần Cảnh"), nen chi sua trong chuong da kiem tra."""
    ovr = json.loads((HERE / "name-overrides.json").read_text(encoding="utf-8"))
    out = defaultdict(list)
    for r in ovr.get("theo_chuong", []):
        sau = r"(?! xuất hiện trước đây)" if r["sai"] == "Đế Tôn" else ""
        rx = re.compile(rf"(?<![{CHU}])(?<!Đại )(?<!Quỷ ){re.escape(r['sai'])}(?![{CHU}]){sau}")
        for c in r["chuong"]:
            out[int(c)].append((rx, r["dung"]))
    return out


def ap_theo_chuong(p, n, tc, dem):
    for rx, dung in tc.get(int(n), ()):
        p, k = rx.subn(dung, p)
        if k:
            dem["ten_rieng"] += k
    return p


def ap_bang_sua(p, rules, dem):
    for rx, dung, ten, giu in rules:
        if giu is None:
            p, k = rx.subn(dung, p)
        else:
            p, k = rx.subn((lambda m, d=dung: cung_kieu(m.group(), d)) if giu else dung, p)
        if k:
            dem[ten] += k
    return p


# ---------------------------------------------------------------- 6. ngoac kep
def ngoac_kep(p, dem):
    if p.count('"') == 0 or p.count('"') % 2:
        return p
    goc = p
    parts = p.split('"')
    # parts chan: ngoai ngoac, le: trong ngoac
    for i in range(1, len(parts), 2):
        parts[i] = parts[i].strip()
    for i in range(0, len(parts), 2):
        seg = parts[i]
        if i > 0:                                   # sau dau dong ngoac
            if seg and (seg[0].isalnum()):
                seg = " " + seg
            elif seg.startswith(" ") and len(seg) > 1 and seg[1] in ",.;:!?":
                seg = seg.lstrip()
        if i < len(parts) - 1:                      # truoc dau mo ngoac
            if seg and (seg[-1].isalnum() or seg[-1] in ",;:"):
                seg = seg + " "
            seg = re.sub(r"\(\s+$", "(", seg)
        parts[i] = seg
    p = '"'.join(parts)
    if p != goc:
        dem["ngoac_kep"] += 1
    return p


# ---------------------------------------------------------------- 7. viet hoa
TU_TOKEN = re.compile(rf"[{CHU}]+")
LOAI_RIENG = {"nhan_vat", "dia_danh", "the_luc", "bao_vat", "cong_phap"}
HAU_TO = {"giới", "tộc", "tông", "môn", "cung", "điện", "thành", "sơn", "cốc", "phong", "các",
          "lâu", "quốc", "giáo", "phái", "viện", "hải", "châu", "đảo", "lĩnh", "nhai", "động",
          "thị", "gia", "hội", "minh", "điện", "đình", "tự", "quan", "trận", "kiếm", "đao", "kinh",
          "quyết", "thuật", "pháp", "ấn", "chỉ", "quyền", "chưởng"}


def giua_cau(p, i):
    """Vi tri i co nam giua cau (khong phai dau cau / dau loi thoai)?"""
    t = p[:i].rstrip(" ")
    if not t:
        return False
    c = t[-1]
    if c in ".!?\"'([:":
        return False
    return True


class VietHoa:
    def __init__(self, entities, uni=None, bi=None):
        self.uni, self.bi = uni or {}, bi or {}
        self.ent = {}
        for e in entities:
            for ten in [e["name"]] + list(e.get("aliases") or []):
                if len(ten.split()) >= 2 and ten not in self.ent:
                    self.ent[ten] = e.get("kind", "khac")
        self.maxn = 5
        self.hinh = defaultdict(Counter)        # ten -> dang viet giua cau
        self.sau_hoa = Counter()                # ten dung ngay sau mot tu viet hoa (manh cua ten dai hon)
        self.truoc_hoa = Counter()              # ten dung ngay truoc mot tu viet hoa
        self.tu_sau = defaultdict(Counter)      # tu viet thuong dung ngay sau ("ấn" + "ký")
        self.quyet = {}

    def _quet(self, p, chi=None):
        toks = list(TU_TOKEN.finditer(p))
        i = 0
        while i < len(toks):
            hit = None
            for n in range(min(self.maxn, len(toks) - i), 1, -1):
                seg = toks[i:i + n]
                if any(seg[k + 1].start() - seg[k].end() != 1 or p[seg[k].end()] != " " for k in range(n - 1)):
                    continue
                key = " ".join(t.group().lower() for t in seg)
                if key in self.ent and (chi is None or key in chi):
                    hit = (key, seg[0].start(), seg[-1].end(), n)
                    yield hit
                    break
            i += 1

    def hoc(self, p):
        for key, a, b, n in self._quet(p):
            if giua_cau(p, a):
                self.hinh[key][p[a:b]] += 1
                mt = re.search(rf"([{CHU}]+) $", p[:a])
                if mt and mt.group(1)[:1].isupper():
                    self.sau_hoa[key] += 1
                ms = re.match(rf" ([{CHU}]+)", p[b:])
                if ms and ms.group(1)[:1].isupper():
                    self.truoc_hoa[key] += 1
                elif ms:
                    self.tu_sau[key][ms.group(1)] += 1

    def chot(self, bao_cao):
        # hau to: viet hoa hay thuong? quyet theo da so tren toan bo ten rieng
        hau = defaultdict(Counter)
        for key, forms in self.hinh.items():
            if self.ent[key] not in LOAI_RIENG:
                continue
            last = key.split()[-1]
            if last in HAU_TO:
                for f, c in forms.items():
                    if f[:1].isupper() and f.split()[:-1] == [hoa_dau(x) for x in key.split()[:-1]]:
                        hau[last]["hoa" if f.split()[-1][:1].isupper() else "thuong"] += c
        self.hau_hoa = {h: c["hoa"] >= c["thuong"] for h, c in hau.items()}
        bao_cao["hau_to"] = {h: dict(c) for h, c in sorted(hau.items(), key=lambda x: -sum(x[1].values()))}

        for key, forms in self.hinh.items():
            kind = self.ent[key]
            tong = sum(forms.values())
            if tong < 3:
                continue
            words = key.split()
            chuan = [hoa_dau(w) for w in words]
            if words[-1] in self.hau_hoa and not self.hau_hoa[words[-1]] and kind in LOAI_RIENG:
                chuan[-1] = words[-1]
            chuan = " ".join(chuan)
            hoa = {f: c for f, c in forms.items() if f[:1].isupper()}
            so_hoa = sum(hoa.values())
            if not so_hoa:
                continue
            chung_thuc = sum(c for f, c in hoa.items() if f in (chuan, hoa_ten(key)))
            # "thần võ ấn" + "ký", "trầm phong cẩn" + "thận": nua dau cua mot tu ghep -> bo qua
            if self.tu_sau[key] and self.tu_sau[key].most_common(1)[0][1] / tong > 0.5:
                continue
            ti_le_chuan = chung_thuc / so_hoa
            # dau cau chi sua khi giua cau thuat ngu nay da chu yeu viet hoa
            dau_ok = so_hoa / tong >= 0.5
            if kind in LOAI_RIENG:
                if ti_le_chuan < 0.2:
                    continue
                # "tinh vương" trong "Hoắc Tinh vương tử" la manh cua ten khac
                if self.sau_hoa[key] / tong > 0.6:
                    continue
                self.quyet[key] = (chuan, so_hoa / tong >= 0.8 and tong >= 5, dau_ok)
            else:
                if forms.get(hoa_ten(key), 0) / so_hoa < 0.3:
                    continue
                # "cảnh đại" la manh cua "Thánh Cảnh đại viên mãn" -> bo qua
                if self.sau_hoa[key] / tong > 0.4 or self.truoc_hoa[key] / tong > 0.4:
                    continue
                self.quyet[key] = (hoa_ten(key), False, so_hoa / tong >= 0.8)
        bao_cao["viet_hoa_thuat_ngu"] = {
            k: {"chuan": v[0], "sua_ca_chu_thuong": v[1], "loai": self.ent[k],
                "truoc": dict(self.hinh[k].most_common(5))}
            for k, v in sorted(self.quyet.items(), key=lambda x: -sum(self.hinh[x[0]].values()))
            if any(f != v[0] for f in self.hinh[k] if f[:1].isupper() or v[1])
        }

    def sua(self, p, dem):
        out, last = [], 0
        for key, a, b, n in self._quet(p, self.quyet):
            if a < last:
                continue
            f = p[a:b]
            chuan, ca_thuong, dau_ok = self.quyet[key]
            # chu cuoi + chu thuong ngay sau la tu ghep hay gap ("phong vận", "bộ tộc") -> khong dung
            ms = re.match(rf" ([{THUONG}]+)", p[b:])
            if ms:
                cuoi = key.split()[-1]
                if self.bi.get((cuoi, ms.group(1)), 0) > 0.2 * max(1, self.uni.get(cuoi, 0)):
                    continue
            moi = f
            if giua_cau(p, a):
                if f[:1].isupper() or ca_thuong:
                    moi = chuan
            elif not dau_ok:
                pass
            else:
                moi = hoa_dau(chuan) if f[:1].isupper() else f
                if f[:1].isupper():
                    moi = hoa_dau(chuan)
            if moi != f:
                out.append(p[last:a]); out.append(moi); last = b
                dem["viet_hoa_ten"] += 1
        if not out:
            return p
        out.append(p[last:])
        return "".join(out)


def hoa_dau_cau(p, dem):
    goc = p
    # dau doan
    m = re.match(r'^([\s"\'(\[\-–—]*)([' + THUONG + r'])', p)
    if m:
        p = p[:m.start(2)] + m.group(2).upper() + p[m.end(2):]
    # sau . ! ? (khong phai ...)
    p = re.sub(r'((?<!\.)[.!?]["\')\]]?\s+["\'(\[]?)([' + THUONG + r'])',
               lambda m: m.group(1) + m.group(2).upper(), p)
    # dau loi thoai: chu dau sau dau mo ngoac
    if p.count('"') % 2 == 0 and '"' in p:
        parts = p.split('"')
        for i in range(1, len(parts), 2):
            q = parts[i]
            mm = re.match(r'^([\s\'(\[]*)([' + THUONG + r'])', q)
            if mm and not q.startswith("..."):
                # loi thoai ngan kieu tu luan ("kẽo kẹt", "Minh Đế") giua cau -> giu nguyen
                truoc = parts[i - 1].rstrip()
                mo_dau = (not truoc) or truoc[-1] in ":.!?" or i == 1 and not truoc
                if mo_dau:
                    parts[i] = q[:mm.start(2)] + mm.group(2).upper() + q[mm.end(2):]
        p = '"'.join(parts)
    if p != goc:
        dem["viet_hoa_dau_cau"] += 1
    return p


def noi_doan(paras, dem):
    """Doan bat dau bang chu thuong ma doan truoc chua het cau -> noi lai."""
    ra = []
    for p in paras:
        if ra and p[:1].islower() and not re.search(r'[.!?…:"\')\]]$', ra[-1]):
            ra[-1] = ra[-1] + " " + p
            dem["noi_doan"] += 1
        else:
            ra.append(p)
    return ra


def sua_tieu_de(titles):
    """Tieu de chuong: dau cau + ten rieng sai chinh ta. {num: title} -> (moi, so_sua)"""
    rules = nap_bang_sua()
    moi, k = {}, 0
    for n, t in titles.items():
        d = Counter()
        x = ap_theo_chuong(ap_bang_sua(dau_cau(t, d), rules, d), n, nap_theo_chuong(), d)
        moi[n] = x
        k += x != t
    return moi, k


# ---------------------------------------------------------------- dieu phoi
def dem_ngram(chuong):
    """unigram, bigram (chu thuong) + so lan moi tu duoc viet hoa giua cau."""
    uni, bi, hoa = Counter(), Counter(), Counter()
    for paras in chuong.values():
        for p in paras:
            w = TU.findall(p.lower())
            uni.update(w)
            bi.update(zip(w, w[1:]))
            for m in re.finditer(rf"(?<=[{THUONG}] )([{HOA}][{CHU}]*)", p):
                hoa[m.group(1).lower()] += 1
    return uni, bi, hoa


def xu_ly(chuong, entities, log=print):
    """chuong: {num: [doan]} -> (chuong_moi, dem_moi_chuong, bao_cao)"""
    dem = {n: Counter() for n in chuong}
    bao_cao = defaultdict(list)

    log("  hieu dinh 1-2: dau cau, ghi chu LLM, rac")
    for n in chuong:
        chuong[n] = [dau_cau(p, dem[n]) for p in chuong[n]]
    toan_van = "\n".join(p for ps in chuong.values() for p in ps).lower()
    ghi_chu_llm.KIEM_TRA = lambda cum: toan_van.count(cum.lower()) >= 3
    sua_tay = ghi_chu_llm.nap_sua_tay()
    for n in chuong:
        ps = ghi_chu_llm.don(chuong[n], n, dem[n], bao_cao, sua_tay)
        chuong[n] = [p for p in loc_rac(ps, dem[n], bao_cao, n) if p]
    ghi_chu_llm.KIEM_TRA = None
    del toan_van

    log("  hieu dinh 3: thong ke bigram + chu Han")
    uni, bi, hoa = dem_ngram(chuong)
    ch = ChuHan(uni, bi, hoa)
    for paras in chuong.values():
        for p in paras:
            if HAN.search(p):
                ch.hoc_chu_thich(p)
    for n in chuong:
        chuong[n] = [ch.sua(p, dem[n], n, bao_cao) if HAN.search(p) else p for p in chuong[n]]
        chuong[n] = [ch.sua_chu_la(p, dem[n], n, bao_cao) if CHU_LA.search(p) else p for p in chuong[n]]
    bao_cao["chu_han_hoc_tu_chu_thich"] = {k: v.most_common(3) for k, v in ch.hoc.items()}
    bao_cao["chu_han_khong_tra_duoc"] = ch.chua_ro.most_common()

    log("  hieu dinh 4-6: ten rieng, chinh ta, ngoac kep")
    rules = nap_bang_sua()
    tc = nap_theo_chuong()
    for n in chuong:
        chuong[n] = [ngoac_kep(ap_theo_chuong(ap_bang_sua(p, rules, dem[n]), n, tc, dem[n]), dem[n]) for p in chuong[n]]

    log("  hieu dinh 7: viet hoa")
    vh = VietHoa(entities, uni, bi)
    for paras in chuong.values():
        for p in paras:
            vh.hoc(p)
    vh.chot(bao_cao)
    for n in chuong:
        ps = noi_doan(chuong[n], dem[n])
        ps = [hoa_dau_cau(vh.sua(p, dem[n]), dem[n]) for p in ps]
        chuong[n] = ps
    return chuong, dem, dict(bao_cao)
