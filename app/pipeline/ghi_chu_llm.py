#!/usr/bin/env python3
"""Don ghi chu cua LLM dich con sot trong nguyen van (goi tu hieu_dinh.py).

Trang nguon dich truyen bang LLM va de lot ca phan "suy nghi" cua model:
  *(Lưu ý: Đã lọc bỏ toàn bộ các ký tự tiếng Trung...)*            -> ca doan
  Minh Điện Thất Tội Sát Thần (Raw: ... -> ...)                     -> ngoac giua cau
  "Thả chậm." -> "Khoan đã." (Sửa lại cho tự nhiên)                -> giu ve phai
  - Dịch chuẩn xác, mượt mà, ... giữ nguyên HTML tags              -> lo prompt dau chuong
  Trương Hán Phong... à nhầm, Trương Nhược Trần -> ...              -> sua tay (hieu-dinh/sua-tay.json)
Them rac cua chinh trang nguon (quang cao app, "đề cử quyển"...).

Quy tac chi danh vao dau hieu chac chan cua ghi chu (raw, glossary, ->, HTML,
"tiếng Trung"...); van truyen khong bao gio dung nhung tu do.
"""
import json, re
from pathlib import Path

CFG = Path(__file__).resolve().parent / "hieu-dinh"

# tu khoa chi xuat hien trong ghi chu cua model, khong co trong van truyen
META = re.compile(
    r"(?i)(\braw\b|glossary|->|=>|\bnote\b|chú thích|lưu ý|ghi chú|chỉnh lại|sửa lại|sửa thành|"
    r"\bsửa\s*:|^\s*sai\b|hán việt|chữ hán|tiếng trung|ký tự trung|giữ nguyên (?:hoặc|theo|tên|hán)|"
    r"tùy (?:ngữ|bối) cảnh|nguyên tác|dịch (?:là|sát|thoát|chuẩn|sang|nghĩa)|hoặc dịch|"
    r"chuẩn hóa|chuyển ngữ|chuyển thành|nhớ (?:quy tắc|chuẩn)|zhou|\bs\s*:|lời nhắn của tác giả|"
    r"đã được dịch|dịch giả|bản dịch|nhầm)")

# "Lưu ý: ..." (co dau hai cham), hoac "*(Hết chương)*" (boc trong * / ngoac)
DOAN_GHI_CHU = re.compile(r"(?i)^[\s*(\[]*(lưu ý|note|chú thích|chú ý|ghi chú)[^:\"]{0,25}:")
DOAN_BOC = re.compile(
    r"(?i)^[*(\[][\s*(\[]*(hết chương|phần tiếp theo|phần kết thúc|kết thúc phần|đoạn quảng cáo|"
    r"hai chương gộp|hôm nay hai chương|sửa lại|thuật ngữ chính|nhân vật & đại từ|tiến hành dịch|lưu ý)")
LO_PROMPT = re.compile(
    r"(?i)(html|ký tự trung quốc|tiếng trung|glossary|dịch máy|công cụ dịch|đại từ nhân xưng|"
    r"rác chuyển ngữ|chuẩn hóa hán việt|nội dung dịch|văn phong cổ phong|\(vạn cổ thần đế\))")
RAC_NGUON = re.compile(
    r"(?i)(thông báo quan trọng của bản trạm|app tiểu thuyết|công chúng hiệu|meinvmei|"
    r"đề cử quyển|hãy chú ý theo dõi tài khoản|khuyên các đạo hữu sáng mai|wechat|weibo|"
    r"công chúng (?:hiệu|hào)|tài khoản (?:chính thức|công khai|công cộng|công chúng)|feitianyu|"
    r"official account|thư hữu đại bản doanh|video hào|nhận (?:hồng bao|bao lì xì))")


def _bo_ngoac(p, dem):
    """Bo cac ngoac (...) ma noi dung la ghi chu. Xu ly ngoac long nhau."""
    out, i, n = [], 0, len(p)
    while i < n:
        if p[i] == "(":
            sau, j = 1, i + 1
            while j < n and sau:
                sau += {"(": 1, ")": -1}.get(p[j], 0)
                j += 1
            if sau == 0:
                trong = p[i + 1:j - 1]
                if META.search(trong) or trong.strip().startswith("*"):
                    # bo ca khoang trang dung truoc ngoac
                    while out and out[-1] == " ":
                        out.pop()
                    dem["llm_ngoac"] += 1
                    i = j
                    continue
        out.append(p[i])
        i += 1
    q = "".join(out)
    q = re.sub(r" {2,}", " ", q)
    q = re.sub(r" +([,.;:!?])", r"\1", q)
    return q.strip()


# ham kiem tra mot cum co xuat hien trong truyen khong (hieu_dinh gan vao khi chay ca truyen)
KIEM_TRA = None


def _sua_theo_ngoac(p, dem):
    """'Trương Tấn (sửa thành Trương Nhược Trần)' -> 'Trương Nhược Trần';
    'kiếp thứ sáu (chỉnh lại: kiếp thứ bảy)' -> 'kiếp thứ bảy'."""
    rx = re.compile(r"\((?:sửa thành|sửa lại|sửa|chỉnh lại|chỉnh sửa|sai|nhầm)(?:\s+theo [^:()]{1,20})?\s*[:,]?\s*"
                    r"([^()/]{1,60}?)\)", re.I)
    for _ in range(6):
        m = rx.search(p)
        if not m:
            break
        r = m.group(1).strip()
        if "->" in r:
            a, r = r.split("->")[0].strip(), r.split("->")[-1].strip()
            # model doi sang ten khac: chi nhan neu ten moi co that trong truyen
            if a != r and not (len(r.split()) >= 2 and KIEM_TRA and KIEM_TRA(r)):
                p = p[:m.start()].rstrip() + p[m.end():]
                dem["llm_ngoac"] += 1
                continue
        w = r.split()
        truoc = p[:m.start()].rstrip()
        tw = truoc.split(" ")
        k = 0
        for i in range(1, min(len(tw), 7) + 1):
            if re.search(r"[,.;!?:\"]$", tw[-i]) and i > 1:
                break
            if w and tw[-i].strip(",.") == w[0]:
                k = i
        if not k and w and w[0][:1].isupper():   # ten sai viet hoa ngay truoc ngoac
            i = 1
            while i <= min(len(tw), 6) and tw[-i][:1].isupper():
                k = i
                i += 1
        if k and w:
            dau = " ".join(tw[:len(tw) - k])
            p = (dau + " " if dau else "") + r + p[m.end():]
        else:
            p = truoc + p[m.end():]
        dem["llm_ngoac"] += 1
    return p


def _mui_ten(p, dem):
    """'"A" -> "B"' / 'cau sai -> cau dung': giu ve phai (ban model da sua)."""
    # "Trương Nhược Trần -> Trương Nhược Trần," giua cau: giu ten sau
    p2 = re.sub(rf"({TEN})\s*->\s*(?={TEN})", "", p)
    if p2 != p:
        dem["llm_mui_ten"] += 1
        p = p2
    if p.count("->") != 1:
        return p
    trai, phai = (x.strip() for x in p.split("->"))
    if not phai or phai.startswith("*"):
        dem["llm_mui_ten"] += 1
        return trai
    tt = trai.split()
    hoa = sum(1 for x in tt if x[:1].isupper()) / max(1, len(tt))
    chac = (trai.endswith(('"', '”', "!", "?")) and phai.startswith(('"', '“'))) \
        or tt[:2] == phai.split()[:2] or hoa > 0.6 or re.search(r"[^\x00-\u024F\u1E00-\u1EFF\s\"'.,!?()-]", trai)
    if chac:
        dem["llm_mui_ten"] += 1
        return phai
    return p


def nap_sua_tay():
    p = CFG / "sua-tay.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("chuong", {})


def don(paras, n, dem, bao_cao, sua_tay):
    """Tra ve danh sach doan da don. n: so chuong."""
    st = sua_tay.get(str(n), {})
    # 1. sua tay: thay chuoi chinh xac, xoa doan theo chuoi mo dau
    if st:
        moi = []
        bo_tu = st.get("xoa_dau_chuong_den")
        dang_bo = bool(bo_tu)
        n_dau = st.get("xoa_n_doan_dau", 0)
        dem["llm_doan"] += min(n_dau, len(paras))
        for p in paras[n_dau:]:
            if dang_bo:
                if bo_tu in p:
                    p = p[p.index(bo_tu):]       # cat phan prompt dinh lien dau doan
                    dang_bo = False
                else:
                    dem["llm_doan"] += 1
                    continue
            if any(p.startswith(x) for x in st.get("xoa_doan", [])):
                dem["llm_doan"] += 1
                continue
            for a, b in st.get("thay", []):
                if a in p:
                    p = p.replace(a, b)
                    dem["llm_sua_tay"] += 1
            moi.append(p)
        paras = moi
    ra = []
    for p in paras:
        goc = p
        s = p.strip()
        if s in ("*", "* *", "**"):
            dem["llm_doan"] += 1
            continue
        if RAC_NGUON.search(s):
            dem["rac"] += 1
            bao_cao["rac"].append(f"c{n}: {s[:120]}")
            continue
        if DOAN_GHI_CHU.match(s) or DOAN_BOC.match(s):
            dem["llm_doan"] += 1
            bao_cao["llm_doan"].append(f"c{n}: {s[:160]}")
            continue
        if s.startswith("- ") and "->" in s:            # dong glossary
            dem["llm_doan"] += 1
            continue
        if "(" in p:
            p = _sua_theo_ngoac(p, dem)
            p = _bo_ngoac(p, dem)
        # lo prompt: xet SAU khi bo ngoac, de doan truyen chi chua ghi chu trong ngoac khong bi xoa
        if LO_PROMPT.search(p) and not _co_thoai(p):
            dem["llm_doan"] += 1
            bao_cao["llm_doan"].append(f"c{n}: {s[:160]}")
            continue
        if "->" in p:
            p = _mui_ten(p, dem)
        p = go_nham(p, dem)
        # sao markdown thua: '* "Huyền Hoàng Thánh Thương!"'
        p = re.sub(r"^\*\s+(?=\")", "", p)
        p = re.sub(r"(?<!\.)\.\.(?!\.)", ".", p)
        p = re.sub(r"([?!])\.(?!\.)", r"\1", p)
        if not re.search(r"\w", p) and (p != goc or p.strip() in ("<", ">", "·", "-", '"')):
            dem["llm_doan"] += 1
            continue
        if p != goc and len(bao_cao["llm_sua"]) < 600:
            bao_cao["llm_sua"].append(f"c{n}: {goc[:200]}  ==>  {p[:200]}")
        ra.append(p)
    return ra


def _co_thoai(s):
    return s.count('"') >= 2 and not s.startswith("(")

# ---------------------------------------------------------------- "à nhầm"
# Model tu sua ngay trong cau: "Trương Hướng Diệp — à nhầm, Trương Nhược Trần — Trương Nhược Trần vừa nghe"
HOA = "A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐĨŨƠƯẠẢẤẦẨẬẮẰẲẶẸẺẼẾỀỂỆỈỊỌỎỐỒỔỘỚỜỞỢỤỦỨỪỬỰỲỴỶỸ"
CHU = HOA + "a-zàáâãèéêìíòóôõùúýăđĩũơưạảấầẩậắằẳặẹẻẽếềểệỉịọỏốồổộớờởợụủứừửựỳỵỷỹ"
NHAM = re.compile(rf"(?:,\s*)?(?<![{CHU}])(?:à nhầm|ơ không|à không|nhớ lộn|Nhớ lộn|ý lộn|(?<=[—–\-] )nhầm|(?<=\.\.\. )nhầm)(?![{CHU}])[,:]?\s*")
GACH = r"\s*(?:\.\.\.|…|—|–|-)\s*"
TEN = rf"[{HOA}][{CHU}]*(?: [{HOA}][{CHU}]*){{0,4}}"


def _gop_lap(p):
    """'Trương Nhược Trần — Trương Nhược Trần vừa' -> 'Trương Nhược Trần vừa'"""
    p = re.sub(rf"(?<![{CHU}])({TEN})(?:{GACH}\1(?![{CHU}]))+", r"\1", p)
    # "Trương Tông Chủ... Trương Nhược Trần" (cung chu dau, noi bang ...) -> giu ten sau
    return re.sub(rf"(?<![{CHU}])([{HOA}][{CHU}]*)((?: [{HOA}][{CHU}]*){{1,3}}){GACH}(?=\1 [{HOA}])", "", p)


def _hoa_sau_cham(p):
    return re.sub(rf'((?<!\.)[.!?]["”]?\s+["“]?)([{CHU[len(HOA):]}])', lambda m: m.group(1) + m.group(2).upper(), p)


def go_nham(p, dem):
    if not NHAM.search(p):
        return p
    goc = p
    for _ in range(12):
        m = NHAM.search(p)
        if not m:
            break
        trai, phai = p[:m.start()], p[m.end():]
        if "không" in m.group():
            ten_trai = re.search(rf"{TEN}{GACH}?,?\s*$", trai)
            if not (phai[:1].isupper() and ten_trai and re.search(r"(\.\.\.|…|—|–|-|,)\s*$", trai)):
                # loi nhan vat tu sua ("lưỡng bại câu thương, à không, tam bại"): giu nguyen
                p = p[:m.start()] + p[m.start():m.end()].replace("không", "kh\u200bông") + p[m.end():]
                continue
        trai = re.sub(rf"{GACH}$", "", trai)
        ym = re.match(r"([^,.;!?\"…—–(]+)", phai)
        y = ym.group(1).split() if ym else []
        y0 = y[0] if y else ""
        w = trai.split(" ")
        # tim diem cat ben trai, khong vuot qua dau cau / dau phay
        han = 0
        for i in range(1, min(len(w), 10) + 1):
            if i > 1 and re.search(r"[,.;!?\":]$", w[-i]):
                break
            han = i
        k = 0
        for i in range(1, han + 1):               # 1) cat tu chu trung voi chu dau ve phai
            if w[-i].strip(".…—–-") == y0:
                k = i
        if not k and y0[:1].isupper():            # 2) ve phai la ten: cat tu dau cum viet hoa cuoi cung
            i = 1
            while i <= han and w[-i][:1].isupper():
                k = i
                i += 1
        if not k:                                 # 3) cum thuong: bo cung so tu (toi da 6)
            k = min(len(y), 6, han) or 1
        p = " ".join(w[:len(w) - k]) + (" " if k < len(w) else "") + phai
        p = _gop_lap(p)
    p = p.replace("kh\u200bông", "không")
    p = re.sub(r" {2,}", " ", p).replace(" ,", ",").strip()
    if p == goc:
        return p
    p = _hoa_sau_cham(p)
    if p[:1].islower():
        p = p[:1].upper() + p[1:]
    if p != goc:
        dem["llm_nham"] += 1
    return p
