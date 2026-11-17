#!/usr/bin/env python3
"""Buoc 2b: don ung vien tho.

  1. Nuot manh vun : "lôn giới" bi nuot boi "côn lôn giới" (cung so lan xuat hien)
  2. Gop bi danh   : "nhược trần" <- "trương nhược trần" (ten rut gon cua cung nhan vat)
  3. Bo rac        : cum tu thong dung lot luoi

Xuat: web/data/entities.json.gz  (danh sach da gop, moi muc co aliases[])
"""
import gzip, json, re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "app" / "web" / "data"

ABSORB_RATIO = 0.82   # A nam trong B va count(A) >= 0.82*count(B) -> A chi la manh vun cua B
ALIAS_RATIO  = 0.25   # A la hau to cua B, A dung doc lap nhieu -> bi danh, khong nuot

# cum pho bien khong phai ten rieng
BLACK_RE = re.compile(r"^(thật |rất |vô cùng |không |đã |cũng |lại )")
BLACK = {
    "thập nhị", "thập nhị phẩm", "tam thập", "nhị thập", "ngũ thập",
    "mấy ngàn", "mấy vạn", "mấy trăm", "nhiều năm", "trong nháy mắt",
}

def main():
    with gzip.open(DATA / "entities-raw.json.gz", "rt", encoding="utf-8") as f:
        raw = json.load(f)
    cands = [e for e in raw["entities"]
             if e["name"] not in BLACK and not BLACK_RE.match(e["name"])]
    cands.sort(key=lambda e: (-e["n"], -e["count"]))   # dai truoc, nhieu truoc

    by_name = {e["name"]: e for e in cands}
    absorbed, alias_of = set(), {}

    # dung chi muc nguoc: am tiet -> cac ten chua no, de khong phai so khop O(n^2)
    syl_index = defaultdict(list)
    for e in cands:
        for s in e["name"].split(" "):
            syl_index[s].append(e["name"])

    for e in cands:                       # e = ung vien dai (B)
        if e["name"] in absorbed:
            continue
        parts = e["name"].split(" ")
        subs = set()
        for ln in range(1, len(parts)):
            for i in range(len(parts) - ln + 1):
                subs.add(" ".join(parts[i:i + ln]))
        for sub in subs:
            s = by_name.get(sub)
            if s is None or sub in absorbed or s["n"] < 2:
                continue
            ratio_inside = e["count"] / max(s["count"], 1)
            if ratio_inside >= ABSORB_RATIO:
                absorbed.add(sub)                       # manh vun thuan tuy
            elif ratio_inside >= ALIAS_RATIO and sub == " ".join(parts[-len(sub.split(" ")):]):
                alias_of.setdefault(sub, e["name"])     # ten rut gon -> bi danh

    # --- Tu chuc nang tieng Viet lot luoi o buoc trich xuat ---
    # VI TRI QUYET DINH NGHIA, nen khong dung mot danh sach chung:
    #   "các" dung cuoi la 閣 (gac/lau): "phi thiên các" la the luc that
    #   "các" dung dau la dai tu:        "các hạ" = "ngai", khong phai ten rieng
    #   "bổn nguyên" la 本源 (ban nguyen) that, nhung "bổn hoàng" la "trẫm"
    TIEN_TO_CAM = set("ở khắp đám bọn lũ cùng kẻ các mỗi từng dám xin".split())
    HAU_TO_CAM  = set("bỗng lóe loé chợt liền ngay vừa mới lại vẫn còn rốt "
                      "cười nói thấy nghe nhìn biết".split())
    BAT_KY_CAM  = set("hỏi".split())
    BON_DAI_TU  = set("hoàng thiên vương tộc đế hậu quân tòa toà cung môn nhân sứ tiêu".split())

    tu_chuc_nang = set()
    for e in cands:
        am = e["name"].split(" ")
        if am[0] in TIEN_TO_CAM or am[-1] in HAU_TO_CAM or any(w in BAT_KY_CAM for w in am):
            tu_chuc_nang.add(e["name"])
        elif am[0] == "bổn" and len(am) > 1 and am[1] in BON_DAI_TU:
            tu_chuc_nang.add(e["name"])       # dai tu nhan xung, khong phai ten rieng

    # "trương nhược trần hỏi" = ten rieng + dong tu, khong phai thuc the rieng
    TAIL_VERBS = set("""
    nói cười hỏi đáp quát gầm hét nhìn liếc gật lắc bước đi đứng ngồi nằm
    nghĩ biết hiểu cảm nhớ quên vung giơ nắm buông thu phất rút vỗ chắp cúi
    ngẩng quay xoay tới đến về ra vào lên xuống cũng lại vẫn đã đang sẽ
    """.split())
    tail_junk = set()
    for e in cands:
        parts = e["name"].split(" ")
        if len(parts) >= 3 and parts[-1] in TAIL_VERBS and " ".join(parts[:-1]) in by_name:
            tail_junk.add(e["name"])
        if len(parts) >= 3 and parts[0] in TAIL_VERBS and " ".join(parts[1:]) in by_name:
            tail_junk.add(e["name"])

    out = []
    for e in cands:
        name = e["name"]
        if name in absorbed or name in alias_of or name in tail_junk or name in tu_chuc_nang:
            continue
        aliases = sorted([a for a, canon in alias_of.items() if canon == name],
                         key=lambda a: -by_name[a]["count"])
        total = e["count"] + sum(by_name[a]["count"] for a in aliases)
        out.append({
            "name": name,
            "aliases": aliases,
            "count": e["count"],
            "total": total,
            "kind": e["kind"],
            "cap": e["cap"],
        })

    out.sort(key=lambda e: -e["total"])
    with gzip.open(DATA / "entities.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"entities": out}, f, ensure_ascii=False, separators=(",", ":"))

    print(f"ung vien tho : {len(cands)}")
    print(f"nuot manh vun: {len(absorbed)}")
    print(f"gop bi danh  : {len(alias_of)}")
    print(f"bo ten+dongtu: {len(tail_junk)}")
    print(f"bo tu chuc nang: {len(tu_chuc_nang)}")
    print(f"con lai      : {len(out)}")
    print("\ntop 25 sau khi don:")
    for e in out[:25]:
        al = ("  <- " + ", ".join(e["aliases"][:3])) if e["aliases"] else ""
        print(f"  {e['total']:>7}  {e['kind']:<10} {e['name']}{al}")

if __name__ == "__main__":
    main()
