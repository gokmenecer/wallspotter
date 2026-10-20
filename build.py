#!/usr/bin/env python3
"""WallSpotter static site generator.

Reads data/wallpapers.csv and pages/*.html, writes the finished site to _site/.
Run `python3 build.py`. Pillow (pip install pillow) is used to make thumbnails for wallpapers stored in the repo.
"""
import csv, hashlib, html, json, re, shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
PREFIX = CFG.get("path_prefix", "").rstrip("/")
BASE = CFG["base_url"].rstrip("/") + PREFIX
# changes whenever style.css changes, so browsers fetch the new version instead of a cached one
CSS_VER = hashlib.md5((ROOT / "static" / "assets" / "style.css").read_bytes()).hexdigest()[:8]
JS_VER = hashlib.md5((ROOT / "static" / "assets" / "site.js").read_bytes()).hexdigest()[:8]


def with_prefix(text):
    """Point site-relative links at PREFIX (used while testing on username.github.io/repo/)."""
    if not PREFIX:
        return text
    text = re.sub(r'((?:href|src|action|data-fallback)=")/(?!/)', rf"\1{PREFIX}/", text)
    text = re.sub(r'(srcset="[^"]*)', lambda m: re.sub(r'(^srcset="|, )/(?!/)', rf"\1{PREFIX}/", m[1]), text)
    return text.replace('url=/', f'url={PREFIX}/').replace('location.replace("/', f'location.replace("{PREFIX}/')

CATEGORIES = {
    "originals": {"slug": "originals", "name": "WallSpotter Originals", "single": "Original Wallpaper"},
    "mobile": {"slug": "mobile-wallpaper", "name": "Mobile Wallpapers", "single": "Mobile Wallpaper"},
    "desktop": {"slug": "desktop-wallpaper", "name": "Desktop Wallpapers", "single": "Desktop Wallpaper"},
}
PIN_SIZE = re.compile(r"(https://i\.pinimg\.com/)(\d+x|originals)(/.+)$")
esc = html.escape


# ---------- data ----------
def load_wallpapers():
    rows = []
    with open(ROOT / "data" / "wallpapers.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r = {k: (v or "").strip() for k, v in r.items()}
            if not r.get("slug") or not r.get("image"):
                continue
            if r["category"] not in CATEGORIES:
                raise SystemExit(f"Unknown category '{r['category']}' for {r['slug']} (use originals, mobile or desktop)")
            r["title"] = r.get("title") or CATEGORIES[r["category"]]["single"]
            r["url"] = f"/{r['slug']}/"
            m = PIN_SIZE.match(r["image"])
            if m:
                r["thumb"] = f"{m[1]}236x{m[3]}"
                r["thumb2x"] = f"{m[1]}474x{m[3]}"
                r["large"] = f"{m[1]}736x{m[3]}"
                r["full"] = f"{m[1]}originals{m[3]}"
            else:
                r["thumb"] = r["thumb2x"] = r["large"] = r["full"] = r["image"]
                stem = Path(r["image"]).with_suffix("")
                for size in ("thumb", "large"):
                    if (ROOT / "static" / f"{stem}-{size}.jpg".lstrip("/")).exists():
                        r[size] = f"{stem}-{size}.jpg"
                r["thumb2x"] = r["large"]
                if r["thumb"] == r["image"] and r["image"].startswith("/"):
                    # no hand-made thumbnail: one is generated at build time
                    r["thumb"] = r["thumb2x"] = f"/assets/thumbs/{Path(r['image']).stem}.jpg"
                    r["_make_thumb"] = True
                    try:
                        from PIL import Image
                        with Image.open(ROOT / "static" / r["image"].lstrip("/")) as im:
                            r["wide"] = im.width > im.height
                    except ImportError:
                        pass
                    if r.get("wide"):
                        # big desktop originals: show a lighter 1920px copy on the page, keep the full file for download
                        r["large"] = f"/assets/thumbs/{Path(r['image']).stem}-1920.jpg"
            r["wide"] = r.get("wide") or r["category"] == "desktop"
            rows.append(r)
    slugs = [r["slug"] for r in rows]
    dupes = {s for s in slugs if slugs.count(s) > 1}
    if dupes:
        raise SystemExit(f"Duplicate slugs in wallpapers.csv: {', '.join(sorted(dupes))}")
    rows.sort(key=lambda r: (r["date"], natural_key(r["slug"])), reverse=True)
    return rows


def natural_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


# ---------- layout ----------
def head_tags(title, desc, path, image=None):
    full_title = f"{title} | {CFG['site_name']}" if title else f"{CFG['site_name']} | {CFG['tagline']}"
    img = image or BASE + "/assets/img/og-logo.png"
    if img.startswith("/"):
        img = BASE + img
    ga = CFG.get("google_analytics", [])
    ga_tags = ""
    if ga:
        cfg_lines = "".join(f"gtag('config','{g}');" for g in ga)
        ga_tags = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga[0]}"></script>'
                   f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
                   f"gtag('js',new Date());{cfg_lines}</script>")
    ads = ""
    if CFG.get("adsense_client"):
        ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={CFG["adsense_client"]}" '
               f'crossorigin="anonymous"></script>')
    cf = ""
    if CFG.get("cloudflare_analytics_token"):
        cf = ("<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
              f"data-cf-beacon='{{\"token\": \"{CFG['cloudflare_analytics_token']}\"}}'></script>")
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{BASE}{path}">{'<meta name="robots" content="noindex">' if PREFIX else ''}
<meta property="og:site_name" content="{esc(CFG['site_name'])}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{BASE}{path}">
<meta property="og:image" content="{esc(img)}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0e0f12">
<link rel="icon" href="/assets/img/favicon.png">
<link rel="apple-touch-icon" href="/assets/img/favicon.png">
<link rel="preconnect" href="https://i.pinimg.com">
<link rel="stylesheet" href="/assets/style.css?v={CSS_VER}">
<script>document.documentElement.classList.add('js')</script>
<script defer src="/assets/site.js?v={JS_VER}"></script>
{ga_tags}
{ads}
{cf}"""


def nav(active=""):
    items = [("/", "Home", "home"), ("/originals/", "Originals", "originals"), ("/mobile-wallpaper/", "Mobile", "mobile"),
             ("/desktop-wallpaper/", "Desktop", "desktop"), ("/about-us/", "About", "about")]
    links = "".join(f'<a href="{u}"{" aria-current=\"page\"" if k == active else ""}>{t}</a>' for u, t, k in items)
    return f"""<header class="top">
  <a class="brand" href="/"><img src="/assets/img/logo.png" alt="{esc(CFG['site_name'])}" width="855" height="76"></a>
  <nav>{links}</nav>
</header>"""


def footer():
    social = "".join(f'<a href="{esc(u)}" rel="noopener">{esc(n)}</a>' for n, u in CFG.get("social", {}).items())
    return f"""<footer class="foot">
  <div class="foot-links">
    <a href="/about-us/">About Us</a><a href="/about-wallpapers/">About Wallpapers</a>
    <a href="/363-2/contact-us/">Contact</a><a href="/privacy-policy/">Privacy Policy</a>
    <a href="/terms-conditions/">Terms &amp; Conditions</a><a href="/sitemap/">Sitemap</a>
  </div>
  <div class="foot-social">{social}</div>
  <p>&copy; {date.today().year} {esc(CFG['site_name'])}. <a href="/originals/">Originals</a> are created by WallSpotter; other wallpapers are shared from our <a href="{esc(CFG['social'].get('Pinterest', '#'))}" rel="noopener">Pinterest boards</a>.</p>
</footer>"""


def page(title, desc, path, body, active="", image=None, extra_head=""):
    return f"""<!doctype html>
<html lang="en">
<head>
{head_tags(title, desc, path, image)}
{extra_head}
</head>
<body>
<a class="rail rail-l" href="/mobile-wallpaper/" tabindex="-1">Mobile Wallpapers &middot; Phone &middot; 9:20</a>
<a class="rail rail-r" href="/desktop-wallpaper/" tabindex="-1">Desktop Wallpapers &middot; PC &middot; 16:9</a>
{nav(active)}
<main>
{body}
</main>
{footer()}
</body>
</html>
"""


def card(w, eager=False):
    loading = "eager" if eager else "lazy"
    srcset = f' srcset="{esc(w["thumb"])} 1x, {esc(w["thumb2x"])} 2x"' if w["thumb"] != w["thumb2x"] else ""
    cls = "card" + (" wide" if w.get("wide") else "")
    cap = (f'<span class="card-cap">{esc(w["title"])}</span>'
           if w["title"] != CATEGORIES[w["category"]]["single"] else "")
    return (f'<a class="{cls}" href="{w["url"]}"><img src="{esc(w["thumb"])}"{srcset} '
            f'alt="{esc(w["title"])}" loading="{loading}" decoding="async">{cap}</a>')


def grid(items):
    return '<div class="grid">' + "".join(card(w, i < 6) for i, w in enumerate(items)) + "</div>"


def write(path, content):
    target = OUT / path.lstrip("/")
    if path.endswith("/"):
        target = target / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(with_prefix(content), encoding="utf-8")


def redirect(from_path, to_path):
    to = BASE + to_path
    write(from_path, f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Redirecting…</title><link rel="canonical" href="{to}">
<meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url={to_path}">
<script>location.replace("{to_path}"+location.hash)</script></head>
<body><a href="{to_path}">Continue</a></body></html>""")


def make_thumbs(walls, width=480):
    """Create small preview images for wallpapers stored in the repo (static/...)."""
    todo = [w for w in walls if w.get("_make_thumb")]
    if not todo:
        return
    from PIL import Image
    for w in todo:
        src = ROOT / "static" / w["image"].lstrip("/")
        dst = OUT / w["thumb"].lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGB")
            if w.get("wide"):
                big = im.copy()
                big.thumbnail((1920, 1920), Image.LANCZOS)
                big.save(OUT / w["large"].lstrip("/"), "JPEG", quality=84, optimize=True, progressive=True)
            tw = width * 2 if w.get("wide") else width
            im.thumbnail((tw, tw * 4), Image.LANCZOS)
            im.save(dst, "JPEG", quality=82, optimize=True, progressive=True)


# ---------- build ----------
def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    walls = load_wallpapers()
    make_thumbs(walls)
    sitemap_urls = ["/"]

    # Home
    intro = (ROOT / "pages" / "_home-intro.html").read_text(encoding="utf-8")
    originals = [w for w in walls if w["category"] == "originals"]
    originals_block = ""
    if originals:
        originals_block = (f'<div class="section-head"><h2 class="section-title">WallSpotter Originals</h2>'
                           f'<a href="/originals/">See all &rarr;</a></div>'
                           f'<p class="count">Wallpapers designed by us — free to download.</p>{grid(originals[:10])}')
    show = [w for w in originals if not w.get("wide")][:8] or walls[:6]
    slides = "".join(f'<img src="{esc(w["thumb2x"])}" alt="" {"class=\"on\" " if i == 0 else ""}loading="{"eager" if i < 2 else "lazy"}">'
                     for i, w in enumerate(show))
    showcase = f"""<a class="showcase" href="/originals/" aria-label="WallSpotter Originals">
  <div class="phone"><div class="screen">{slides}</div><span class="island"></span>
  <span class="lock"><span class="lock-date" data-date></span><span class="lock-time" data-time>9:41</span></span></div>
</a>"""
    body = f"""<section class="hero hero-split"><div class="hero-text"><h1>{esc(CFG['site_name'])}</h1><p>{esc(CFG['tagline'])} — free mobile and desktop wallpapers.</p>
<p class="hero-links"><a class="btn" href="/originals/">Explore Originals</a><a class="btn ghost" href="/mobile-wallpaper/">Mobile</a><a class="btn ghost" href="/desktop-wallpaper/">Desktop</a></p></div>
{showcase}</section>
{originals_block}
<h2 class="section-title">Latest wallpapers</h2>
{grid([w for w in walls if w["category"] != "originals"])}
<details class="about-box"><summary>About wallpapers</summary>{intro}</details>"""
    write("/", page("", CFG["description"], "/", body, "home"))

    # Category pages
    for key, c in CATEGORIES.items():
        items = [w for w in walls if w["category"] == key or (key == "desktop" and w["category"] == "originals" and w.get("wide"))]
        if not items:
            continue
        lead = (" Original wallpapers designed by WallSpotter, free to download for personal use."
                if key == "originals" else "")
        body = f'<h1 class="section-title">{c["name"]}</h1><p class="count">{len(items)} wallpapers.{lead}</p>{grid(items)}'
        desc = (f"Original phone wallpapers designed by {CFG['site_name']}, free to download." if key == "originals"
                else f"Free {c['name'].lower()} curated by {CFG['site_name']}.")
        write(f"/{c['slug']}/", page(c["name"], desc,
                                    f"/{c['slug']}/", body, key))
        redirect(f"/category/{c['slug']}/", f"/{c['slug']}/")
        sitemap_urls.append(f"/{c['slug']}/")

    # Wallpaper pages
    for i, w in enumerate(walls):
        same = [x for x in walls if x["category"] == w["category"] and x is not w]
        idx = walls.index(w)
        newer = walls[idx - 1] if idx > 0 else None
        older = walls[idx + 1] if idx + 1 < len(walls) else None
        start = same.index(older) if older in same else 0
        related = (same[start:] + same[:start])[:12]
        cat = CATEGORIES[w["category"]]
        pin = f'<a class="btn ghost" href="{esc(w["pin"])}" rel="noopener">View on Pinterest</a>' if w.get("pin") else ""
        is_orig = w["category"] == "originals"
        desc_html = f'<p class="desc">{esc(w["description"])}</p>' if w.get("description") else ""
        if is_orig:
            button = (f'<a class="btn" href="{esc(w["full"])}" download="wallspotter-{w["slug"]}.jpg">Download</a>')
            hint = (f"Free for personal use as a {'desktop' if w.get('wide') else 'phone'} wallpaper. &copy; WallSpotter.")
        else:
            button = (f'<a class="btn" id="dl" href="{esc(w["full"])}" data-fallback="{esc(w["large"])}" '
                      f'target="_blank" rel="noopener">Open full size</a>')
            hint = "Open the full-size image, then press and hold (phone) or right-click (computer) to save it."
        preview_btn = ""
        preview_dialog = ""
        if not w.get("wide"):
            preview_btn = '<button class="btn ghost" type="button" data-preview>Preview on lock screen</button>'
            preview_dialog = f"""<dialog class="preview" id="preview" aria-label="Lock screen preview">
  <div class="phone phone-lg"><div class="screen"><img class="on" src="{esc(w['large'])}" alt="{esc(w['title'])} on a phone lock screen"></div>
  <span class="island"></span><span class="lock"><span class="lock-date" data-date></span><span class="lock-time" data-time>9:41</span></span>
  <span class="lock-bar"></span></div>
  <button class="preview-close" type="button" data-close aria-label="Close preview">&times;</button>
</dialog>"""
        pager = ""
        if newer:
            pager += f'<a href="{newer["url"]}">&larr; Newer</a>'
        if older:
            pager += f'<a href="{older["url"]}">Older &rarr;</a>'
        body = f"""<article class="single {'is-wide' if w.get('wide') else ''}">
  <div class="single-img"><img src="{esc(w['large'])}" alt="{esc(w['title'])}" decoding="async"></div>
  <div class="single-info">
    <p class="crumb"><a href="/{cat['slug']}/">{cat['name']}</a></p>
    <h1>{esc(w['title'])}</h1>
    <time datetime="{w['date']}">{date.fromisoformat(w['date']).strftime('%d %B %Y')}</time>
    {desc_html}
    <div class="actions">
      {button}
      {preview_btn}
      {pin}
    </div>
    <p class="hint">{hint}</p>
    <nav class="pager">{pager}</nav>
  </div>
</article>
{preview_dialog}
<h2 class="section-title">More {cat['name'].lower()}</h2>
{grid(related)}
<script>(function(){{var a=document.getElementById('dl');if(!a||a.href===a.dataset.fallback)return;var i=new Image();i.onerror=function(){{a.href=a.dataset.fallback}};i.src=a.href;}})();</script>"""
        meta_desc = w.get("description") or f"{w['title']} — free download from {CFG['site_name']}."
        write(w["url"], page(w["title"], meta_desc, w["url"], body,
                             w["category"], image=w["large"]))
        sitemap_urls.append(w["url"])
        redirect(f"{w['url']}amp/", w["url"])

    # Static pages (pages/*.html, first line is "<!-- Title | description -->")
    for f in sorted((ROOT / "pages").glob("*.html")):
        if f.name.startswith("_"):
            continue
        raw = f.read_text(encoding="utf-8")
        m = re.match(r"<!--\s*(.+?)\s*\|\s*(.+?)\s*-->\s*", raw)
        title, desc = (m[1], m[2]) if m else (f.stem.replace("-", " ").title(), CFG["description"])
        content = raw[m.end():] if m else raw
        path = "/363-2/contact-us/" if f.stem == "contact-us" else f"/{f.stem}/"
        content = content.replace("{{WEB3FORMS_KEY}}", esc(CFG.get("web3forms_key", "")))
        write(path, page(title, desc, path, f'<article class="prose"><h1>{esc(title)}</h1>{content}</article>',
                         "about" if f.stem == "about-us" else ""))
        sitemap_urls.append(path)

    # HTML sitemap
    links = "".join(f'<li><a href="{w["url"]}">{esc(w["title"])}</a> <span>{w["date"]}</span></li>' for w in walls)
    body = f"""<article class="prose"><h1>Sitemap</h1>
<h2>Pages</h2><ul><li><a href="/">Home</a></li><li><a href="/mobile-wallpaper/">Mobile Wallpapers</a></li>
<li><a href="/desktop-wallpaper/">Desktop Wallpapers</a></li><li><a href="/about-us/">About Us</a></li>
<li><a href="/about-wallpapers/">About Wallpapers</a></li><li><a href="/363-2/contact-us/">Contact Us</a></li>
<li><a href="/privacy-policy/">Privacy Policy</a></li><li><a href="/terms-conditions/">Terms &amp; Conditions</a></li></ul>
<h2>Wallpapers</h2><ul class="sitemap-list">{links}</ul></article>"""
    write("/sitemap/", page("Sitemap", f"All pages and wallpapers on {CFG['site_name']}.", "/sitemap/", body))
    sitemap_urls.append("/sitemap/")

    # Old WordPress addresses
    for old, new in CFG.get("redirects", {}).items():
        redirect(old, new)
    pages_count = 10
    for n in range(2, pages_count + 1):
        redirect(f"/page/{n}/", "/")

    # 404
    write("/404.html", page("Page not found", "Page not found.", "/404.html",
                            f'<section class="hero"><h1>Page not found</h1><p>This page has moved or no longer exists.</p></section>{grid(walls[:12])}'))

    # sitemap.xml, robots.txt, CNAME
    today = date.today().isoformat()
    lastmod = {w["url"]: w["date"] for w in walls}
    xml = "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{lastmod.get(u, today)}</lastmod></url>" for u in sitemap_urls)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xml}</urlset>',
        encoding="utf-8")
    robots = "User-agent: *\nDisallow: /\n" if PREFIX else f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n"
    (OUT / "robots.txt").write_text(robots, encoding="utf-8")
    if CFG.get("custom_domain") and not PREFIX:
        (OUT / "CNAME").write_text(CFG["custom_domain"] + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Built {len(walls)} wallpapers, {len(sitemap_urls)} indexed pages -> {OUT}")


if __name__ == "__main__":
    build()
