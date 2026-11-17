#!/usr/bin/env python3
"""Buoc 6: chuan hoa ten rieng trong tom tat, dua tren chi muc 5.878 thuc the.

Doc checkpoint (khong sua), ghi ra web/data/summaries.json.gz + bao cao.
An toan khi tien trinh tom tat con dang chay.

Sua hai loai loi:
  1. Han-Viet bi dich nghia   "Rừng Phi"        -> "Lâm Phi"
  2. Sai chinh ta am tiet     "Trương Như Trần" -> "Trương Nhược Trần"

  python3 pipeline/chuan_hoa_ten.py --dry-run    # chi bao cao, khong ghi
  python3 pipeline/chuan_hoa_ten.py
"""
import argparse, gzip, json, re, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
CKPT = DATA / "summaries.partial.jsonl"
OVR  = Path(__file__).resolve().parent / "name-overrides.json"

# Am tiet Han-Viet hay bi LLM dich sang nghia thuan Viet.
# nghia thuan Viet -> am tiet Han-Viet goc
GLOSS = {
    "rừng": "lâm", "cây": "mộc", "gỗ": "mộc", "đá": "thạch", "vàng": "kim",
    "nước": "thủy", "lửa": "hỏa", "đất": "địa", "trời": "thiên", "mây": "vân",
    "gió": "phong", "sấm": "lôi", "mưa": "vũ", "tuyết": "tuyết", "băng": "băng",
    "trăng": "nguyệt", "sao": "tinh", "rồng": "long", "cọp": "hổ", "hổ": "hổ",
    "phượng": "phượng", "chim": "điểu", "cá": "ngư", "ngựa": "mã", "trâu": "ngưu",
    "trắng": "bạch", "đen": "hắc", "đỏ": "hồng", "xanh": "thanh", "tím": "tử",
    "biển": "hải", "sông": "giang", "núi": "sơn", "hang": "động", "suối": "tuyền",
    "vua": "vương", "tướng": "tướng", "thần": "thần", "tiên": "tiên", "ma": "ma",
    "máu": "huyết", "xương": "cốt", "tim": "tâm", "mắt": "nhãn", "tay": "thủ",
    "lớn": "đại", "nhỏ": "tiểu", "già": "lão", "mới": "tân", "chín": "cửu",
    "một": "nhất", "hai": "nhị", "ba": "tam", "bốn": "tứ", "năm": "ngũ",
    "sáu": "lục", "bảy": "thất", "tám": "bát", "mười": "thập",
    "đông": "đông", "tây": "tây", "nam": "nam", "bắc": "bắc", "giữa": "trung",
    "sáng": "minh", "tối": "u", "lạnh": "hàn", "nóng": "nhiệt", "sâu": "thâm",
}

def bo_dau(s):
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()

def hoa_ten(s):
    return " ".join(w[:1].upper() + w[1:] for w in s.split(" "))

def khoang_cach(a, b):
    """Levenshtein ngan gon."""
    if a == b: return 0
    if abs(len(a) - len(b)) > 2: return 9
    truoc = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        nay = [i]
        for j, cb in enumerate(b, 1):
            nay.append(min(truoc[j] + 1, nay[j - 1] + 1, truoc[j - 1] + (ca != cb)))
        truoc = nay
    return truoc[-1]


# Nhung am tiet chi khac nhau o dau thanh deu la tu rieng biet trong Han-Viet.
# Tu dong "sua" giua chung se bop meo ten dung thanh ten sai.
CAM_SUA = [
    {"thanh", "thánh", "thành", "thản"}, {"vũ", "võ", "vu"}, {"chúa", "chủ", "chu"},
    {"thiên", "thiến", "thiền", "thiện"}, {"tư", "từ", "tử", "tứ", "thứ"},
    {"hoa", "hóa", "hỏa", "họa"}, {"thư", "thú", "thủ", "thự", "thụ"},
    {"long", "lòng", "lông"}, {"minh", "mình", "mịnh"}, {"đế", "đệ", "đề"},
    {"nhân", "nhan", "nhẫn"}, {"thần", "thanh", "thánh", "thần"}, {"hải", "hái", "hài"}, {"sứ", "sử", "sự", "sư"},
]
DUYET, TU_CHOI, DE_XUAT = {}, {}, {}

def bi_cam(a, b):
    return any(a in nhom and b in nhom for nhom in CAM_SUA)


def nap_duyet():
    """Cap sua chinh ta da duyet. Khong co file -> khong sua chinh ta nao ca."""
    if not OVR.exists():
        return {}, {}
    j = json.loads(OVR.read_text(encoding="utf-8"))
    return j.get("duyet", {}), j.get("tu_choi", {})


def nap_thuc_the():
    with gzip.open(DATA / "index.json.gz", "rt", encoding="utf-8") as f:
        idx = json.load(f)
    canon = {}                      # ten thuong -> so lan nhac (de uu tien)
    for ten, v in idx.items():
        canon[ten] = v["n"]
        for a in v.get("a", []):
            canon.setdefault(a, v["n"])
    return canon


def dung_bang_sua(canon):
    bien_the = {}                   # bien the thuong -> ten chuan thuong

    # 1. Han-Viet bi dich nghia: sinh bien the tu ten chuan
    nguoc = defaultdict(list)
    for viet, han in GLOSS.items():
        nguoc[han].append(viet)
    for ten in canon:
        am = ten.split(" ")
        for i, a in enumerate(am):
            for viet in nguoc.get(a, []):
                bt = am[:i] + [viet] + am[i + 1:]
                k = " ".join(bt)
                if k not in canon:
                    bien_the.setdefault(k, ten)

    # 2. Sai chinh ta am tiet: nhom theo "bo khung" = so am tiet + am dau + am cuoi
    khung = defaultdict(list)
    for ten, n in canon.items():
        am = ten.split(" ")
        if len(am) >= 2:
            khung[(len(am), bo_dau(am[0])[:3], bo_dau(am[-1])[:3])].append((ten, n))
    return bien_the, khung


HOA = "A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐĨŨƠƯẠẢẤẦẨẬẮẰẲẶẸẺẼẾỀỂỆỈỊỌỎỐỒỔỘỚỜỞỢỤỦỨỪỬỰỲỴỶỸ"
THUONG = "a-zàáâãèéêìíòóôõùúýăđĩũơưạảấầẩậắằẳặẹẻẽếềểệỉịọỏốồổộớờởợụủứừửựỳỵỷỹ"
CUM_HOA = re.compile(rf"\b([{HOA}][{THUONG}]+(?:\s+[{HOA}][{THUONG}]+){{1,4}})\b")

def sua_mot(text, canon, bien_the, khung, dem, xac_nhan):
    def thay(m):
        goc = m.group(1)
        thuong = goc.lower()
        # Khong return ngay khi thuong in canon: ban convert go sai ten o nhieu cho,
        # sai du nhieu de NER coi do la thuc the rieng ("trương ngược trần" 1.3k lan
        # ben canh "trương nhược trần" 104k lan). Chi giu nguyen neu khong co ten
        # nao AP DAO hon no ve tan suat.
        tan_suat_goc = canon.get(thuong, 0)
        # (1) bien the dich nghia
        if thuong in bien_the:
            dung = bien_the[thuong]
            dem[f"dịch nghĩa: {goc} → {hoa_ten(dung)}"] += 1
            xac_nhan[goc] = hoa_ten(dung)
            return hoa_ten(dung)
        # (2) sai chinh ta: CHI ap dung cap da duyet trong name-overrides.json
        if thuong in DUYET:
            dung = DUYET[thuong]
            dem[f"chính tả: {goc} → {hoa_ten(dung)}"] += 1
            xac_nhan[goc] = hoa_ten(dung)
            return hoa_ten(dung)
        if thuong in canon or thuong in TU_CHOI:
            return goc                                  # ten that, khong dung toi
        # Khong nam trong danh sach duyet -> ghi lai de nguoi duyet, KHONG tu sua
        am = thuong.split(" ")
        ung = khung.get((len(am), bo_dau(am[0])[:3], bo_dau(am[-1])[:3]), [])
        ung_vien = []
        for ten, n in ung:
            am2 = ten.split(" ")
            khac = [(x, y) for x, y in zip(am, am2) if x != y]
            if len(khac) != 1:
                continue
            sai, dung = khac[0]
            d = khoang_cach(sai, dung)
            if bi_cam(sai, dung):                       # khac dau = tu khac, khong dung
                continue
            # Hai bac: lech 1 ky tu can ten pho bien; lech 2 chi chap nhan cho
            # ten cuc pho bien (nhan vat chinh), noi sai chinh ta la chac chan.
            if not ((d == 1 and n >= 1000) or (d == 2 and n >= 20000)):
                continue
            # Neu chinh no cung la mot muc trong canon, chi sua khi ung vien
            # ap dao han (>=50 lan) — tuc gan nhu chac chan la loi go nguon.
            if tan_suat_goc and n < tan_suat_goc * 50:
                continue
            ung_vien.append((n, ten))
        # nhap nhang giua nhieu ten pho bien -> khong doan bua
        if len(ung_vien) == 1:
            DE_XUAT[thuong] = (ung_vien[0][1], ung_vien[0][0])
        return goc
    return CUM_HOA.sub(thay, text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    global DUYET, TU_CHOI
    DUYET, TU_CHOI = nap_duyet()
    canon = nap_thuc_the()
    bien_the, khung = dung_bang_sua(canon)
    print(f"cặp sửa chính tả đã duyệt : {len(DUYET)}  (từ chối: {len(TU_CHOI)})")
    print(f"thực thể chuẩn : {len(canon):,}")
    print(f"biến thể dịch nghĩa sinh ra: {len(bien_the):,}")

    rows = []
    for line in CKPT.read_text(encoding="utf-8").splitlines():
        try: rows.append(json.loads(line))
        except Exception: pass

    dem = Counter()
    xac_nhan = {}
    ket = {}
    for r in rows:
        ket[str(r["n"])] = sua_mot(r["s"], canon, bien_the, khung, dem, xac_nhan)

    # Luot 2: ten nam trong chuoi hoa dai (vd "Cửu Vương Tử Trương Như Trần")
    # khong duoc tach ra o luot 1. Ap lai cac cap DA XAC NHAN, nen an toan.
    for n, txt in ket.items():
        txt = re.sub(r"\s*\n+\s*", " ", txt)          # tom tat la mot khoi lien mach
        txt = re.sub(r"[ \t]{2,}", " ", txt).strip()
        ket[n] = txt

    for n, txt in ket.items():
        for sai, dung in xac_nhan.items():
            if sai in txt:
                txt = txt.replace(sai, dung)
                dem[f"lượt 2: {sai} → {dung}"] += 1
        ket[n] = txt

    tong = sum(dem.values())
    print(f"chương         : {len(ket):,}")
    print(f"vị trí đã sửa  : {tong:,}\n")
    print("30 sửa đổi nhiều nhất:")
    for k, v in dem.most_common(30):
        print(f"  {v:>4}×  {k}")

    if DE_XUAT:
        dx = {k: {"co_the_la": v[0], "tan_suat_dich": v[1]} for k, v in sorted(DE_XUAT.items())}
        (OVR.parent / "name-proposals.json").write_text(
            json.dumps(dx, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n⚠ {len(DE_XUAT)} cặp chờ duyệt → pipeline/name-proposals.json")
        print("  (chưa sửa gì; chuyển sang mục \"duyet\" trong name-overrides.json nếu đúng)")
        for k, v in list(sorted(DE_XUAT.items()))[:8]:
            print(f"    {k} → {v[0]}?")

    if a.dry_run:
        print("\n(--dry-run: chưa ghi file nào)")
        return
    with gzip.open(DATA / "summaries.json.gz", "wt", encoding="utf-8") as f:
        json.dump(ket, f, ensure_ascii=False, separators=(",", ":"))
    (DATA / "name-fixes.json").write_text(
        json.dumps(dem.most_common(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ web/data/summaries.json.gz  ({len(ket):,} chương)")
    print(f"✓ web/data/name-fixes.json    (nhật ký {len(dem):,} loại sửa)")


if __name__ == "__main__":
    main()
