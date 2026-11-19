#!/usr/bin/env python3
"""Buoc: dong goi ban de deploy — them trang SEO (cong cu toc tim) va
GEO (cong cu trich xuat trit huong sinh, vd GPTBot, ClaudeBot, Perplexity).

Doc chung vao web/data/ voi app.js: chapters.json, summaries.json.gz,
index.json.gz, cooc.json.gz, quotes.json.gz. Khong can shard nguyen van.

Viets ra public/:
  truyen/index.html          gioi thieu tac pham + thong ke + JSON-LD Book
  chuong/N/index.html        tung chuong: tom tat AI + thuc the trong chuong
  wiki/<slug>/index.html tung thuc the duoc trang bo nguong
  seo.css                    chung cho het, khong phu thuoc app.css
  sitemap.xml (+ 3 con)      cho Google/Bing
  llms.txt, llms-full.txt    ban tin machinh cho LLM
  robots.txt                 cho phep tat ca + chi sico
  index.html                 SPA goc, chen description/canonical/og/JSON-LD vao <head>

Nguong trang bo thuc the: n >= 50 va k != 'khac', hoac n >= 500 — chuan
cua nguong Wiki mac dinh, de khong dat thuc the la rap vaoc chi muc cong.

  python3 pipeline/build_seo.py [thumuc-xuat]   # mac dinh: app/public
  SEO_BASE_URL=https://ten-minh.vercel.app python3 pipeline/build_seo.py
"""
import gzip, hashlib, html, json, os, re, sys, unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "app" / "web" / "data"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "app" / "public"

# Dia chi cong khai. Chiinh xac cho canonical/og/sitemap/llms.
BASE = (os.environ.get("SEO_BASE_URL") or "https://vctd.vercel.app").rstrip("/")

GATE_N    = 50     # nguong Wiki mac dinh trong app.js
GATE_BIG  = 500    # thuc the rat hay xuat hien, lam trang tu
TOP_CHAPTER_ENTS = 30
TOP_WIKI_REL     = 10

KIND_LABEL = {
    "nhan_vat": "Nhân vật", "the_luc": "Thế lực",   "dia_danh": "Địa danh",
    "cong_phap": "Công pháp", "bao_vat": "Bảo vật",  "canh_gioi": "Cảnh giới",
    "khac": "Khác",
}
# Cach goi trong cau dinh nghia
KIND_NOM = {
    "nhan_vat": "nhân vật", "the_luc": "thế lực",    "dia_danh": "địa danh",
    "cong_phap": "công pháp", "bao_vat": "bảo vật",  "canh_gioi": "cảnh giới",
    "khac": "khoan mục",
}


def esc(s):
    return html.escape(str(s), quote=True)


def slugify(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("đ", "d").replace("Đ", "D").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "thuc-the"


def title_case(s):
    return re.sub(r"(^|\s)(\w)", lambda m: m.group(1) + m.group(2).upper(), s)


def load():
    def gz(name):
        with gzip.open(DATA / name, "rt", encoding="utf-8") as f:
            return json.load(f)
    meta = json.loads((DATA / "chapters.json").read_text(encoding="utf-8"))
    return meta, gz("summaries.json.gz"), gz("index.json.gz"), gz("cooc.json.gz"), gz("quotes.json.gz")


CSS = """:root{color-scheme:light dark;--bg:#fff;--fg:#1c1813;--mut:#6f6558;--acc:#9c3b22;--line:#e6dfd5;--card:#f7f4ef}
@media (prefers-color-scheme:dark){:root{--bg:#151310;--fg:#e9e3d8;--mut:#9a9184;--acc:#d3705a;--line:#343028;--card:#1e1b16}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.75 Georgia,"Times New Roman",serif}
main{max-width:46rem;margin:0 auto;padding:1.5rem 1.25rem 3rem}
h1{font-size:1.65rem;line-height:1.3;margin:.25rem 0 1.1rem}
h2{font-size:.85rem;font-weight:600;color:var(--mut);letter-spacing:.06em;text-transform:uppercase;margin:1.7rem 0 .55rem;font-family:system-ui,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.crumb{font-size:.85rem;color:var(--mut);font-family:system-ui,sans-serif;margin-bottom:.75rem}
.crumb a{color:var(--mut)}
.kind{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:.05rem .6rem;font-size:.78rem;color:var(--mut);font-family:system-ui,sans-serif;margin-left:.5rem;vertical-align:middle}
.meta{color:var(--mut);font-family:system-ui,sans-serif;font-size:.95rem;margin:0}
ul.ents,ol.ents{list-style:none;padding:0;margin:.25rem 0 0;font-family:system-ui,sans-serif}
ul.ents li,ol.ents li{display:flex;justify-content:space-between;gap:1rem;padding:.3rem 0;border-bottom:1px dashed var(--line);font-size:.95rem}
li .cnt{color:var(--mut);font-size:.85rem;white-space:nowrap}
blockquote{margin:0;padding:.8rem 1rem;background:var(--card);border-left:3px solid var(--acc);border-radius:0 8px 8px 0;font-size:.95rem}
blockquote footer{color:var(--mut);font-size:.85rem;margin-top:.45rem;font-family:system-ui,sans-serif}
.nav{display:flex;justify-content:space-between;gap:1rem;margin-top:2.2rem;font-family:system-ui,sans-serif;font-size:.95rem}
.note{color:var(--mut);font-size:.88rem;font-family:system-ui,sans-serif}
footer{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line);font-size:.85rem;color:var(--mut);font-family:system-ui,sans-serif}
"""

FAVICON = ('data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 44"%3E'
           '%3Crect x="1" y="1" width="42" height="42" rx="11" fill="%23b3402f"/%3E'
           '%3Ctext x="22" y="23" font-size="22" font-family="serif" text-anchor="middle" '
           'dominant-baseline="central" fill="%23fff"%3E%E4%B8%87%3C/text%3E%3C/svg%3E')


def head(cssrel, url, title, desc, ld):
    u = BASE + url
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{u}">
<link rel="icon" href="{FAVICON}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="VCTĐ Tra cứu">
<meta property="og:locale" content="vi_VN">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{u}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="{cssrel}seo.css">
{ld}
</head>"""


def footer_extra():
    return (f'Truyện thuộc về tác giả Phi Thiên Ngư; trang này chỉ chứa bản lược dịch tiếng Việt '
            f'được chuẩn hoá và tóm tắt AI. <a href="{BASE}/">Mở ứng dụng tra cứu toàn tập</a>.')


def page(cssrel, url, title, desc, body, ld):
    return (head(cssrel, url, title, desc, ld) + f"\n<body><main>\n{body}\n"
            f'<footer>{footer_extra()}</footer>\n</main></body></html>\n')


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main(out=None):
    out = Path(out) if out else OUT
    meta, summaries, index, cooc, quotes = load()
    title, author = meta["title"], meta["author"]
    chapters = meta["chapters"]
    total = len(chapters)
    today = date.today().isoformat()
    by_num = {c["n"]: c for c in chapters}

    print(f"SEO/GEO → {out}   (BASE={BASE})")

    # ---- slug + trang bo nguong -------------------------------
    slugs, used = {}, {}
    for name in index:
        base = slugify(name)
        used[base] = used.get(base, 0) + 1
        slugs[name] = base if used[base] == 1 else f"{base}-{used[base]}"
    gate = {n for n, v in index.items()
            if (v["n"] >= GATE_N and v["k"] != "khac") or v["n"] >= GATE_BIG}
    gate = sorted(gate, key=lambda n: -index[n]["n"])
    sl = {n: slugs[n] for n in gate}

    # do chi: chuong -> thuc the xuat hien
    chap_ents = defaultdict(list)
    for n, v in index.items():
        for ch, cnt in v["c"]:
            chap_ents[ch].append((cnt, n))
    for ch in chap_ents:
        chap_ents[ch].sort(key=lambda t: -t[0])

    # ---- css ---------------------------------------------------
    write(out / "seo.css", CSS)

    # ---- /truyen/ ---------------------------------------------
    def ld_graph(items):
        return ('<script type="application/ld+json">' +
                json.dumps({"@context": "https://schema.org", "@graph": items},
                           ensure_ascii=False) + '</script>')

    web = {"@type": "WebSite", "name": "VCTĐ Tra cứu", "url": BASE + "/",
           "inLanguage": "vi",
           "description": f"Công cụ đọc và tra cứu trong trình duyệt cho tiểu thuyết {title}: "
                          f"tóm tắt AI từng chương, wiki {len(gate):,} thực thể, trích dẫn và chat "
                          f"Q&amp;A dẫn nguồn chương."}
    book = {"@type": "Book", "name": title, "author": {"@type": "Person", "name": author},
            "inLanguage": "vi", "genre": "Tiên hiệp", "numberOfPages": total,
            "url": BASE + "/truyen/",
            "description": f"{total:,} chương, {meta['totalWords']:,} từ. "
                           "Mỗi chương kèm tóm tắt AI; wiki theo nhân vật, thế lực, địa danh, "
                           "công pháp, bảo vật, cảnh giới."}

    li_top = "\n".join(
        f'<li><a href="/wiki/{sl[n]}/">{esc(title_case(n))}</a> <span class="cnt">'
        f'{KIND_LABEL[v["k"]]} · {v["n"]:,} lần</span></li>'
        for n, v in ((n, index[n]) for n in gate[:20]))
    open_block = f'<blockquote>{esc(summaries.get("1", ""))}</blockquote>'
    truyen_body = f"""<nav class="crumb"><a href="{BASE}/">Trang chủ</a> › <span>{esc(title)}</span></nav>
<h1>{esc(title)}</h1>
<p class="meta">Tác giả {esc(author)} · {total:,} chương · {meta['totalWords']:,} từ · bản tiếng Việt</p>
<h2>Nội dung trang này</h2>
<ul>
<li><a href="{BASE}/#doc">Đọc truyện</a> — bản chuẩn hoá chạy trong trình duyệt, đọc offline, nhớ vị trí</li>
<li><a href="{BASE}/#muc-luc">Mục lục {total:,} chương</a> — từng chương còn có <a href="/chuong/1/">trang riêng</a> với tóm tắt AI</li>
<li><a href="{BASE}/#tra-cuu">Tra cứu thực thể</a> — {len(gate):,} mục wiki dưới đây, mỗi mục một trang</li>
<li><a href="{BASE}/#chat">Chat hỏi đáp</a> — LLM trả lời kèm dẫn chương</li>
</ul>
<h2>Mở đầu</h2>
{open_block}
<p class="note">Tóm tắt chương 1 · Phi Thiên Ngư — {esc(title)}</p>
<h2>Thực thể tiêu biểu</h2>
<ol class="ents">{li_top}</ol>
<p class="note">Đang hiển thị 20/{len(gate):,} — toàn bộ trong wiki của app hoặc <a href="/llms.txt">llms.txt</a>.</p>"""
    write(out / "truyen" / "index.html",
          page("../", "/truyen/",
               f"{title} — tra cứu & wiki ({total:,} chương)",
               f"Tiểu thuyết {title}, tác giả {author}: {total:,} chương, "
               f"{meta['totalWords']:,} từ. Công cụ đọc, mục lục, wiki thực thể, trích dẫn, chat.",
               truyen_body,
               ld_graph([web, book])))

    # ---- /chuong/N/ -------------------------------------------
    n_ch = 0
    for ch in chapters:
        n, t = ch["n"], ch["t"]
        summ = summaries.get(str(n), "").strip()
        ents = chap_ents.get(n, [])[:TOP_CHAPTER_ENTS]
        items = "\n".join(
            f'<li><a href="/wiki/{sl[x]}/">{esc(title_case(x))}</a> '
            f'<span class="cnt">{c} lần</span></li>'
            for c, x in ents if x in sl)
        more = len(ents) > TOP_CHAPTER_ENTS
        if len(chap_ents.get(n, [])) > TOP_CHAPTER_ENTS:
            more = True
            items += f'<li class="note"><span>{len(chap_ents[n]) - TOP_CHAPTER_ENTS} thực thể khác</span></li>'
        prev = f'<a href="/chuong/{n - 1}/">← Chương {n - 1}</a>' if n > 1 else '<span></span>'
        nxt = (f'<a href="/chuong/{n + 1}/">Chương {n + 1} →</a>'
               if n < total else f'<a href="{BASE}/#doc/{n}">Mở trong app</a>')
        body = f"""<nav class="crumb"><a href="/truyen/">{esc(title)}</a> › <span>Chương {n}</span></nav>
<h1>Chương {n} — {esc(t)}</h1>
<p class="meta">Chương {n}/{total:,} · {ch['w']:,} từ</p>
<h2>Tóm tắt</h2>
<p>{esc(summ) if summ else '—'}</p>
<h2>Thực thể trong chương</h2>
<ol class="ents">{items or '<li class="note">—</li>'}</ol>
<nav class="nav">{prev}<a href="{BASE}/#doc/{n}">Mở trong app</a>{nxt}</nav>"""
        ld = ('<script type="application/ld+json">'
              + json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
                            "itemListElement": [
                                {"@type": "ListItem", "position": 1,
                                 "name": title, "item": BASE + "/truyen/"},
                                {"@type": "ListItem", "position": 2,
                                 "name": f"Chương {n} — {t}",
                                 "item": f"{BASE}/chuong/{n}/"}]},
                            ensure_ascii=False) + "</script>")
        desc = f"Chương {n} “{t}” của tiểu thuyết {title}: " + (summ[:150] + "…" if len(summ) > 150 else summ)
        write(out / "chuong" / str(n) / "index.html",
              page("../../", f"/chuong/{n}/", f"Chương {n} — {t} · {title}", desc, body, ld))
        n_ch += 1

    # ---- /wiki/<slug>/ ---------------------------------------
    def wiki_def(n):
        v = index[n]
        tf = by_num[v["f"]]["t"]
        tl = by_num[v["l"]]["t"]
        top3 = sorted(v["c"], key=lambda p: -p[1])[:3]
        s = (f"{esc(title_case(n))} là {KIND_NOM[v['k']]} trong tiểu thuyết "
             f"“{esc(title)}” của {esc(author)}. Tên này được nhắc "
             f"{v['n']:,} lần, lần đầu ở chương {v['f']} (“{esc(tf)}”), "
             f"lần cuối ở chương {v['l']} (“{esc(tl)}”).")
        if len(v["c"]) >= 2:
            s += " Dày đặc nhất: " + ", ".join(f"chương {c} ({k} lần)" for c, k in top3) + "."
        return s

    n_wiki = 0
    for n in gate:
        v = index[n]
        surl = f"/wiki/{sl[n]}/"
        defsent = wiki_def(n)
        desc = (defsent[:159] + "…") if len(defsent) > 160 else defsent
        alias = v.get("a") or []
        alias_html = (f'<p><b>Bí danh / biến thể:</b> {esc(", ".join(title_case(a) for a in alias))}</p>'
                      if alias else "")
        rel = [x for x in (cooc.get(n) or []) if x in index][:TOP_WIKI_REL]
        rel_html = ""
        if rel:
            lis = "\n".join(
                f'<li><a href="/wiki/{sl[x]}/">{esc(title_case(x))}</a></li>' if x in sl
                else f'<li class="note">{esc(title_case(x))}</li>' for x in rel)
            rel_html = f'<h2>Hay đi cùng</h2><ul class="ents">{lis}</ul>'
        qs = (quotes.get(n) or [])[:2]
        quote_html = ""
        if qs:
            bqs = "\n".join(
                f'<blockquote>“{esc(q["t"])}”<footer>— chương {q["n"]} · '
                f'{esc(by_num[q["n"]]["t"])}</footer></blockquote>' for q in qs)
            quote_html = f'<h2>Trích dẫn trong truyện</h2>{bqs}'
        body = f"""<nav class="crumb"><a href="/truyen/">{esc(title)}</a> › <a href="{BASE}/#wiki">Wiki</a> › <span>{esc(title_case(n))}</span></nav>
<h1>{esc(title_case(n))}<span class="kind">{KIND_LABEL[v['k']]}</span></h1>
<p>{defsent}</p>
{alias_html}
{rel_html}
{quote_html}
<p><a href="{BASE}/#tra-cuu">Tra cứu đầy đủ trong app →</a></p>"""
        ld = ('<script type="application/ld+json">'
              + json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
                            "itemListElement": [
                                {"@type": "ListItem", "position": 1,
                                 "name": title, "item": BASE + "/truyen/"},
                                {"@type": "ListItem", "position": 2,
                                 "name": "Wiki", "item": BASE + "/#wiki"},
                                {"@type": "ListItem", "position": 3,
                                 "name": title_case(n),
                                 "item": BASE + surl}]},
                            ensure_ascii=False) + "</script>")
        write(out / "wiki" / sl[n] / "index.html",
              page("../../", surl, f"{title_case(n)} — wiki {title}", desc, body, ld))
        n_wiki += 1

    # ---- sitemap ---------------------------------------------
    def sm(name, urls):
        rows = "\n".join(f'  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>' for u in urls)
        write(out / name,
              '<?xml version="1.0" encoding="UTF-8"?>\n'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
              f"{rows}\n</urlset>\n")
    sm("sitemap-chuong.xml", [f"{BASE}/chuong/{c['n']}/" for c in chapters])
    sm("sitemap-wiki.xml", [f"{BASE}/wiki/{n}/" for n in gate])
    sm("sitemap-truyen.xml", [BASE + "/truyen/"])
    write(out / "sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f'  <sitemap><loc>{BASE}/sitemap-chuong.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{BASE}/sitemap-wiki.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{BASE}/sitemap-truyen.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          '</sitemapindex>\n')

    # ---- llms.txt + llms-full.txt ----------------------------
    blurb = (f"Công cụ đọc và tra cứu trong trình duyệt cho tiểu thuyết “{title}” "
             f"({total:,} chương, {meta['totalWords']:,} từ, tác giả {author}). "
             f"Mỗi chương có tóm tắt AI; wiki gồm {len(gate):,} thực thể (nhân vật, thế lực, "
             f"địa danh, công pháp, bảo vật, cảnh giới) kèm trích dẫn và chương xuất hiện.")
    wiki_lines = "\n".join(
        f"- [{title_case(n)} ({KIND_LABEL[index[n]['k']].lower()})](/wiki/{n2}/) — "
        f"{index[n]['n']:,} lần, chương {index[n]['f']}–{index[n]['l']}"
        for n, n2 in ((n, sl[n]) for n in gate))
    chap_lines = "\n".join(f"- [Chương {c['n']} — {c['t']}](/chuong/{c['n']}/)" for c in chapters)
    write(out / "llms.txt",
          f"# VCTĐ Tra cứu — {title}\n\n"
          f"> {blurb} Chạy 100% phía khách, đọc offline, không cần tài khoản.\n\n"
          f"## Trang chính\n- [Giới thiệu tác phẩm & thống kê](/truyen/)\n"
          f"- [Ứng dụng (đọc, mục lục, tra cứu, wiki, chat)](/)\n"
          f"- [Toàn bộ tóm tắt + wiki (llms-full.txt)](/llms-full.txt)\n\n"
          f"## Wiki ({len(gate):,} thực thể)\n{wiki_lines}\n\n"
          f"## Chương ({total:,})\n{chap_lines}\n")
    full = [f"# VCTĐ Tra cứu — {title}", "",
            f"{blurb} File này là bản tin cho máy: tóm tắt từng chương và định nghĩa wiki.", "",
            "## Tác phẩm", f"- Tên: {title}", f"- Tác giả: {author}",
            f"- Chương: {total}", f"- Từ: {meta['totalWords']}", "- Ngôn ngữ: tiếng Việt", "",
            "## Tóm tắt chương"]
    for c in chapters:
        full += [f"### Chương {c['n']} — {c['t']}", summaries.get(str(c['n']), "").strip() or "(thiếu)", ""]
    full.append("## Wiki")
    for n in gate:
        full += [f"### {title_case(n)} ({KIND_LABEL[index[n]['k']].lower()})", wiki_def(n).replace("<b>", "").replace("</b>", ""), ""]
    write(out / "llms-full.txt", "\n".join(full))

    # ---- robots.txt ------------------------------------------
    write(out / "robots.txt",
          "# Cho phép mọi bot, kể cả bot LLM (GPTBot, ClaudeBot, PerplexityBot, Google-Extended)\n"
          "User-agent: *\nAllow: /\n\n"
          f"Sitemap: {BASE}/sitemap.xml\n")

    # ---- chen meta vao index.html (ban SPA da copy) ----------
    idx = out / "index.html"
    if idx.exists():
        h = idx.read_text(encoding="utf-8")
        desc = (f"Đọc và tra cứu “{title}” ({total:,} chương) trong trình duyệt: tóm tắt AI từng "
                f"chương, wiki {len(gate):,} thực thể, trích dẫn dẫn chương, chat với LLM. "
                f"Đọc offline, không tài khoản.")
        ld = ld_graph([{**web, "url": BASE + "/"},
                       {**book, "url": BASE + "/truyen/"}])
        og = ("\n".join(f'<meta property="og:{k}" content="{esc(v)}">'
                        for k, v in [("type", "website"), ("site_name", "VCTĐ Tra cứu"),
                                     ("locale", "vi_VN"), ("title", f"{title} — tra cứu"),
                                     ("description", desc), ("url", BASE + "/")])
              + "\n" + "".join(f'<meta name="twitter:{k}" content="{esc(v)}">'
                               for k, v in [("card", "summary"), ("title", f"{title} — tra cứu"),
                                            ("description", desc)]))
        insert = (f'\n<meta name="description" content="{esc(desc)}">\n'
                  f'<link rel="canonical" href="{BASE}/">\n'
                  f'<link rel="icon" href="{FAVICON}">\n{og}\n{ld}\n')
        if '</head>' in h and 'rel="canonical"' not in h:
            idx.write_text(h.replace("</head>", insert + "</head>", 1), encoding="utf-8")

    # ---- tong ket -------------------------------------------
    tot = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"  chuong: {n_ch:,} wiki: {n_wiki:,} (trang bo ngoai nguong: "
          f"{len(index) - n_wiki:,})")
    print(f"  tong public/: {tot / 1048576:.1f} MB")
    print(f"  xem: {BASE}/truyen/  {BASE}/chuong/1/  {BASE}/wiki/{gate[0]}/")
    print(f"  LLM: {BASE}/llms.txt  {BASE}/llms-full.txt")


if __name__ == "__main__":
    main()
