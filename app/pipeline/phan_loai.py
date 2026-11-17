#!/usr/bin/env python3
"""Buoc 7: phan loai lai thuc the bang TOM TAT thay vi ban convert.

Ban convert viet hoa lung tung va ngu phap vo nghia, nen mau ngu canh chay kem.
Tom tat do LLM viet thi dung ngu phap va viet hoa chuan, nen cung mot mau ngu
canh cho tin hieu sach hon han.

Chi ghi de khi BANG CHUNG DU MANH; con lai giu nguyen ket qua cu.
  python3 pipeline/phan_loai.py --dry-run
"""
import argparse, gzip, json, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"

NHAN = {"nhan_vat":"Nhân vật","the_luc":"Thế lực","dia_danh":"Địa danh",
        "cong_phap":"Công pháp","bao_vat":"Bảo vật","canh_gioi":"Cảnh giới","khac":"Khác"}

# Mau ngu canh: (loai, bieu thuc). {X} la cho cua ten thuc the.
MAU = [
 ("nhan_vat", r"{X}\s+(nói|cười|hỏi|đáp|quát|gầm|nhìn|gật đầu|lắc đầu|xuất thủ|động thủ|ra tay|"
              r"giết|đánh bại|tấn công|truy đuổi|bị thương|tử vong|chết|xuất hiện cùng|dẫn|phái|"
              r"ra lệnh|quyết định|nhận ra|phát hiện|thu được|đồng ý|từ chối|tiết lộ|thừa nhận)"),
 ("nhan_vat", r"(cùng|và|với|gặp|cứu|giết|đánh bại|truy đuổi|bắt|tha|cầu xin|bái)\s+{X}\b"),
 ("nhan_vat", r"{X}\s+(và|cùng)\s+[A-ZÀ-Ỹ]"),
 ("dia_danh", r"(tại|ở|đến|tới|về|rời|trong|ngoài|vào|khắp|quanh|từ)\s+{X}\b"),
 ("dia_danh", r"{X}\s+(sụp đổ|rung chuyển|bị phá|mở ra|đóng lại)"),
 ("the_luc",  r"(của|thuộc|gia nhập|phản bội|dẫn quân|đệ tử|trưởng lão|tộc nhân|người của)\s+{X}\b"),
 ("the_luc",  r"{X}\s+(xuất binh|tấn công|bao vây|truy sát|phái|cử|tuyên bố)"),
 ("cong_phap",r"(thi triển|vận|dùng|luyện|tu luyện|lĩnh ngộ|phá giải|thông thạo)\s+{X}\b"),
 ("cong_phap",r"{X}\s+(tâm pháp|kiếm pháp|công pháp|thần thông)"),
 ("bao_vat",  r"(thu được|lấy|trao|tặng|cầm|rút|luyện hóa|hấp thu|nuốt|dùng)\s+{X}\b"),
 ("bao_vat",  r"{X}\s+(phát sáng|rung động|bay ra|vỡ nát|được luyện)"),
 ("canh_gioi",r"(đạt|đột phá|tiến vào|thăng lên|tu luyện đến|dừng ở)\s+{X}\b"),
 ("canh_gioi",r"{X}\s+(đại viên mãn|sơ kỳ|trung kỳ|hậu kỳ|đỉnh phong)"),
]

NGUONG_PHIEU = 10     # it nhat bao nhieu lan khop moi duoc xet
NGUONG_TY_LE = 0.65   # loai thang phai chiem bao nhieu phan tram so phieu


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    with gzip.open(DATA / "index.json.gz", "rt", encoding="utf-8") as f:
        idx = json.load(f)
    sums = json.load(gzip.open(DATA / "summaries.json.gz", "rt", encoding="utf-8"))

    def van_ban_cua(v):
        """Chi ghep tom tat cac chuong thuc the co mat — nhanh hon quet toan bo
        4211 tom tat cho tung thuc the hang nghin lan."""
        return "\n".join(s for c, _ in v["c"] if (s := sums.get(str(c))))

    # chi xet thuc the thuc su xuat hien trong tom tat
    ung = [(t, v) for t, v in idx.items() if v["n"] >= 80]
    print(f"xét {len(ung):,} thực thể (≥80 lần nhắc) trên {len(sums):,} tóm tắt")

    doi, giu, phieu_it, bi_veto = {}, 0, 0, []
    for ten, v in ung:
        hoa = " ".join(w[:1].upper() + w[1:] for w in ten.split(" "))
        toan_van = van_ban_cua(v)
        if hoa not in toan_van:
            continue
        # ranh gioi tu hai dau, neu khong "Trường Sinh" se an phieu cua "Hứa Trường Sinh"
        X = r"(?<![\wÀ-ỹ])" + re.escape(hoa) + r"(?![\wÀ-ỹ])"
        phieu = Counter()
        for loai, mau in MAU:
            phieu[loai] += len(re.findall(mau.replace("{X}", X), toan_van))
        del toan_van
        tong = sum(phieu.values())
        if tong < NGUONG_PHIEU:
            phieu_it += 1
            continue
        loai, sl = phieu.most_common(1)[0]
        if sl / tong < NGUONG_TY_LE:
            giu += 1                       # bang chung mau thuan -> khong dong vao
            continue
        if v["k"] != "khac":
            # da co tin hieu hinh thai (hau to ...giới, ...tông, ...đế) thi giu,
            # ngu canh khong duoc lat: "Thiên Đình Giới" la dia danh du cau van
            # noi ve no nhu mot nhan vat.
            if loai != v["k"]:
                bi_veto.append((ten, v["k"], loai))
            continue
        if loai != v["k"]:
            doi[ten] = (v["k"], loai, sl, tong)

    print(f"đổi loại : {len(doi):,}")
    print(f"giữ nguyên vì bằng chứng mâu thuẫn : {giu:,}")
    print(f"giữ nguyên vì quá ít dẫn chứng     : {phieu_it:,}")
    print(f"hậu tố Hán-Việt phủ quyết ngữ cảnh : {len(bi_veto):,}")
    for t, cu, moi in bi_veto[:5]:
        print(f"    giữ {t} là {NHAN[cu]} (ngữ cảnh đoán {NHAN[moi]})")

    chuyen = Counter(f"{NHAN[c]} → {NHAN[m]}" for c, m, _, _ in doi.values())
    print("\nCHUYỂN NHIỀU NHẤT:")
    for k, n in chuyen.most_common(10): print(f"  {n:>5}×  {k}")
    print("\nVÍ DỤ (ưu tiên thực thể nổi bật):")
    vd = sorted(doi.items(), key=lambda kv: -idx[kv[0]]["n"])[:14]
    for ten, (cu, moi, sl, tong) in vd:
        print(f"  {ten:<26} {NHAN[cu]:<10} → {NHAN[moi]:<10} ({sl}/{tong} phiếu, {idx[ten]['n']:,} lần nhắc)")

    if a.dry_run:
        print("\n(--dry-run: chưa ghi gì)"); return
    for ten, (_, moi, _, _) in doi.items():
        idx[ten]["k"] = moi
    with gzip.open(DATA / "index.json.gz", "wt", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))
    (DATA / "kind-changes.json").write_text(json.dumps(
        {t: {"cu": NHAN[c], "moi": NHAN[m], "phieu": f"{s}/{g}"} for t, (c, m, s, g) in sorted(doi.items())},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ index.json.gz cập nhật · nhật ký ở kind-changes.json")
    print("theo loại sau khi đổi:", dict(Counter(NHAN[v["k"]] for v in idx.values()).most_common()))

if __name__ == "__main__":
    main()
