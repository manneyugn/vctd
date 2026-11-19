#!/usr/bin/env python3
"""Buoc 9: dong goi ban TRA CUU de deploy (Vercel, Netlify, Cloudflare Pages...).

Ban nay KHONG kem nguyen van truyen. No chi gom chi muc, wiki, tom tat va cac
file tinh cua app — khoang 2,4 MB thay vi 31,4 MB.

  python3 pipeline/build_public.py
  → thu muc public/  : deploy thang, khong can build step, khong can backend
"""
import gzip, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = ROOT / "public"

NGUON_URL  = "https://webnovel.vn/van-co-than-de-truyen/451/"
NGUON_TEN  = "webnovel.vn"

# Nhung gi duoc mang len: chi muc la du kien, tom tat la noi dung moi do AI viet.
# shard-*.json.gz (nguyen van truyen) KHONG nam trong danh sach nay.
FILE_APP = ["index.html", "app.css", "app.js", "sw.js"]
FILE_DATA = ["index.json.gz", "summaries.json.gz", "cooc.json.gz",
             "quotes.json.gz", "clean-log.json.gz"]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)

    for f in FILE_APP:
        shutil.copy2(WEB / f, OUT / f)
    for f in FILE_DATA:
        src = WEB / "data" / f
        if src.exists():
            shutil.copy2(src, OUT / "data" / f)
        else:
            print(f"  ! thiếu {f}, bỏ qua")

    # chapters.json duoc danh dau che do tra cuu + dan nguon
    meta = json.loads((WEB / "data" / "chapters.json").read_text(encoding="utf-8"))
    meta["mode"] = "tra-cuu"
    meta["sourceUrl"] = NGUON_URL
    meta["sourceName"] = NGUON_TEN
    (OUT / "data" / "chapters.json").write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Service Worker: bo cac lo chuong khoi danh sach luu san
    sw = (OUT / "sw.js").read_text(encoding="utf-8").replace("vctd-v1", "vctd-tracuu-v1")
    (OUT / "sw.js").write_text(sw, encoding="utf-8")

    # Header cho file nen: nhieu CDN thay duoi .gz la tu gan Content-Encoding,
    # khien trinh duyet giai nen san. Khai bao ro de server khong doan.
    (OUT / "vercel.json").write_text(json.dumps({
        "headers": [
            {"source": "/data/(.*).json.gz",
             "headers": [
                 {"key": "Content-Type", "value": "application/octet-stream"},
                 {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"},
             ]},
            {"source": "/data/chapters.json",
             "headers": [{"key": "Cache-Control", "value": "public, max-age=3600"}]},
            {"source": "/sw.js",
             "headers": [{"key": "Cache-Control", "value": "no-cache"}]},
        ],
        "cleanUrls": True,
    }, indent=1), encoding="utf-8")

    # Netlify / Cloudflare Pages doc file _headers
    (OUT / "_headers").write_text(
        "/data/*.json.gz\n"
        "  Content-Type: application/octet-stream\n"
        "  Cache-Control: public, max-age=31536000, immutable\n"
        "/sw.js\n"
        "  Cache-Control: no-cache\n", encoding="utf-8")

    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    # SEO/GEO: truyen/, chuong/, wiki/, sitemap, llms + meta vao index.html
    import build_seo
    build_seo.main(out=OUT)

    tong = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"\n✓ public/  —  {tong/1048576:.2f} MB")
    for f in sorted(OUT.rglob("*")):
        if f.is_file():
            print(f"    {str(f.relative_to(OUT)):<28}{f.stat().st_size/1024:>9,.0f} KB")
    day = sum(f.stat().st_size for f in (WEB / "data").glob("shard-*.json.gz"))
    print(f"\n  (không kèm {day/1048576:.1f} MB nguyên văn — bản đầy đủ vẫn chạy cục bộ bằng ./run.sh)")
    print("\nDeploy:  cd public && vercel deploy --prod")


if __name__ == "__main__":
    main()
