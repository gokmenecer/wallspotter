"""Share new WallSpotter wallpapers on Instagram and Threads (Facebook sharing is off).

Runs in GitHub Actions after the site is deployed (see .github/workflows/social.yml).

  python scripts/social.py post      share every originals wallpaper not yet in data/social-posted.json;
                                     wallpapers listed in data/series.json go out together as one carousel
  python scripts/social.py unpublish delete the posts of wallpapers removed from data/wallpapers.csv
  python scripts/social.py check     only test that the saved tokens still work
  python scripts/social.py refresh   renew the Threads token (it lasts 60 days) and save it again
  python scripts/social.py stats     rank our Threads posts of the last 30 days -> data/threads-top.json
  python scripts/social.py daily     stats every day, plus refresh when the token is 6+ days old

The access tokens live encrypted in data/social-secrets.enc; the key is the SOCIAL_KEY repository secret.
"""
import csv, json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://www.wallspotter.com"
FB_PAGE_ID = "1417764814757989"
IG_USER_ID = "17841400298077993"
GRAPH = "https://graph.facebook.com/v24.0"
THREADS = "https://graph.threads.net/v1.0"
STATE = ROOT / "data" / "social-posted.json"
SECRETS = ROOT / "data" / "social-secrets.enc"
SERIES = ROOT / "data" / "series.json"
HASHTAG_FILE = ROOT / "data" / "hashtags.json"   # optional {"<slug>": "#a #b #c #d #e"} written by the daily task
FACEBOOK_ENABLED = False           # 2026-11-19: stopped (0 reactions in 100+ posts, inflated the stats with bot visits)
SAVE_NOTE = "📌 Save this so you can find it when it's time for a new wallpaper."
THREADS_TOPIC = "Wallpaper"
THREADS_TOPIC_2 = "4K Wallpaper"   # a reply under each Threads post carries this second topic
REPLY_FROM = "2026-11-10"          # only wallpapers from this date on get that reply


# ---------- secrets ----------
def _openssl(args, data):
    key = os.environ.get("SOCIAL_KEY")
    if not key:
        raise SystemExit("SOCIAL_KEY is not set")
    return subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-a", "-A",
                           *args, "-pass", "env:SOCIAL_KEY"], input=data, capture_output=True, check=True).stdout


def load_secrets():
    return json.loads(_openssl(["-d"], SECRETS.read_bytes().strip() + b"\n"))


def save_secrets(sec):
    SECRETS.write_bytes(_openssl([], json.dumps(sec).encode()) + b"\n")


# ---------- http ----------
def call(method, endpoint, **params):
    data = urllib.parse.urlencode(params).encode()
    if method in ("GET", "DELETE"):
        req = urllib.request.Request(endpoint + "?" + data.decode(), method=method)
    else:
        req = urllib.request.Request(endpoint, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {endpoint} -> {e.code}: {body}") from None


# ---------- captions ----------
def wallpapers():
    with open(ROOT / "data" / "wallpapers.csv", newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("slug") and r.get("category") == "originals"]
    rows.reverse()  # the CSV has newest lines first; post oldest first
    return rows


def is_wide(w):
    from PIL import Image
    with Image.open(ROOT / "static" / w["image"].lstrip("/")) as im:
        return im.width > im.height


def image_url(w, wide):
    if wide:
        return f"{SITE}/assets/thumbs/{Path(w['image']).stem}-1920.jpg"
    return f"{SITE}/assets/social/{w['slug']}.jpg"


def short(text, limit):
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


# topic word in title/description -> hashtag (first matches win; up to 3 per post)
TOPIC_TAGS = [
    (("neon",), "#neonwallpaper"), (("gradient",), "#gradientwallpaper"),
    (("mountain", "peak", "valley", "hill"), "#mountainwallpaper"),
    (("ocean", "sea", "wave", "tide", "water", "lake"), "#oceanwallpaper"),
    (("sunset", "sunrise", "dawn", "dusk", "golden hour"), "#sunsetwallpaper"),
    (("star", "galaxy", "space", "cosmic", "nebula", "planet", "moon", "eclipse", "black hole"), "#spacewallpaper"),
    (("forest", "tree", "pine", "leaf", "leaves", "fern"), "#naturewallpaper"),
    (("flower", "rose", "petal", "blossom", "bloom"), "#flowerwallpaper"),
    (("rain", "drop", "glass", "frost"), "#rainwallpaper"),
    (("desert", "dune", "sand"), "#desertwallpaper"),
    (("minimal", "calm", "soft", "simple"), "#minimalwallpaper"),
    (("abstract", "layer", "paint", "fluid", "liquid", "swirl"), "#abstractwallpaper"),
    (("3d", "render", "sculpt", "stone", "marble", "metal"), "#3dwallpaper"),
    (("dark", "night", "midnight", "shadow", "black"), "#darkwallpaper"),
    (("blue",), "#bluewallpaper"), (("purple", "violet", "lavender"), "#purplewallpaper"),
    (("pink", "rose"), "#pinkaesthetic"), (("orange", "amber", "ember", "fire"), "#orangeaesthetic"),
    (("green", "emerald", "teal"), "#greenaesthetic"), (("aesthetic", "dreamy", "pastel"), "#aestheticwallpaper"),
]


def hashtags(items, wide):
    """Five hashtags made for this post: format tag, up to three topic tags, #aiart."""
    override = json.loads(HASHTAG_FILE.read_text()) if HASHTAG_FILE.exists() else {}
    if len(items) == 1 and override.get(items[0]["slug"]):
        return override[items[0]["slug"]]
    text = " ".join(f"{w['title']} {w['description']}" for w in items).lower()
    tags = ["#desktopwallpaper" if wide else "#iphonewallpaper"]
    for words, tag in TOPIC_TAGS:
        if len(tags) == 4:
            break
        if tag not in tags and any(wd in text for wd in words):
            tags.append(tag)
    for filler in ("#4kwallpaper" if wide else "#lockscreen", "#wallpaper", "#aestheticwallpaper"):
        if len(tags) < 4 and filler not in tags:
            tags.append(filler)
    return " ".join(tags + ["#aiart"])


def captions(w, wide):
    title, desc, link = w["title"], w["description"], f"wallspotter.com/{w['slug']}"
    tags = hashtags([w], wide)
    fb = f"{title} ✨\n\n{desc}\n\nFree full-resolution download 👉 {SITE}/{w['slug']}/"
    ig = f"{title} ✨\n\n{desc}\n\nFree full-resolution download at wallspotter.com (link in bio) 🖼️\n\n{SAVE_NOTE}\n\n{tags}"
    tail = f"\n\nFree full-res download 👉 {link}"
    th = f"{title} ✨\n\n" + short(desc, 500 - len(title) - len(tail) - 6) + tail
    return {"facebook": fb, "instagram": ig, "threads": th}


def series_captions(series, items):
    n, title, q = len(items), series["title"], series.get("question", "").strip()
    intro = series.get("intro", "").strip()
    head = f"{title} · {n} new wallpapers ✨"
    tail = "\n\nFree full-res downloads 👉 wallspotter.com"
    body = "\n\n".join(x for x in (intro, q) if x)
    th = head + "\n\n" + short(body, 500 - len(head) - len(tail) - 4) + tail
    ig = (f"{head}\n\n{body}\n\nSwipe to see all {n} → free full-resolution downloads at wallspotter.com "
          f"(link in bio) 🖼️\n\n{SAVE_NOTE}\n\n{hashtags(items, False)}")
    return {"instagram": ig, "threads": th}


# ---------- platforms ----------
def post_facebook(sec, url, text):
    r = call("POST", f"{GRAPH}/{FB_PAGE_ID}/photos", url=url, message=text, access_token=sec["page_token"])
    return r.get("post_id") or r["id"]


def _ig_wait(tok, c, what, tries=60):
    for _ in range(tries):
        st = call("GET", f"{GRAPH}/{c}", fields="status_code", access_token=tok).get("status_code")
        if st == "FINISHED":
            return
        if st == "ERROR":
            raise RuntimeError(f"Instagram could not process the {what}")
        time.sleep(5)
    raise RuntimeError(f"Instagram is still processing the {what}")


def _ig_publish(tok, c):
    return call("POST", f"{GRAPH}/{IG_USER_ID}/media_publish", creation_id=c, access_token=tok)["id"]


def post_instagram(sec, url, text):
    tok = sec["page_token"]
    c = call("POST", f"{GRAPH}/{IG_USER_ID}/media", image_url=url, caption=text, access_token=tok)["id"]
    _ig_wait(tok, c, "image", 30)
    return _ig_publish(tok, c)


def post_instagram_reel(sec, video_url, text):
    tok = sec["page_token"]
    c = call("POST", f"{GRAPH}/{IG_USER_ID}/media", media_type="REELS", video_url=video_url, caption=text,
             share_to_feed="true", access_token=tok)["id"]
    _ig_wait(tok, c, "video")
    return _ig_publish(tok, c)


def post_instagram_carousel(sec, urls, text):
    tok = sec["page_token"]
    kids = []
    for u in urls:
        k = call("POST", f"{GRAPH}/{IG_USER_ID}/media", image_url=u, is_carousel_item="true", access_token=tok)["id"]
        _ig_wait(tok, k, "carousel image", 30)
        kids.append(k)
    c = call("POST", f"{GRAPH}/{IG_USER_ID}/media", media_type="CAROUSEL", children=",".join(kids),
             caption=text, access_token=tok)["id"]
    _ig_wait(tok, c, "carousel", 30)
    return _ig_publish(tok, c)


def _th_wait(tok, c, what):
    for _ in range(30):
        st = call("GET", f"{THREADS}/{c}", fields="status", access_token=tok).get("status")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads could not process the {what} ({st})")
        time.sleep(5)


def _th_create(tok, **params):
    """Create a Threads container in the "Wallpaper" topic (falls back to no topic)."""
    try:
        return call("POST", f"{THREADS}/me/threads", topic_tag=THREADS_TOPIC, access_token=tok, **params)["id"]
    except RuntimeError as e:
        print(f"::warning::Threads topic tag not accepted, posting without it: {e}")
        return call("POST", f"{THREADS}/me/threads", access_token=tok, **params)["id"]


def post_threads(sec, url, text):
    tok = sec["threads_token"]
    c = _th_create(tok, media_type="IMAGE", image_url=url, text=text)
    _th_wait(tok, c, "image")
    return call("POST", f"{THREADS}/me/threads_publish", creation_id=c, access_token=tok)["id"]


def post_threads_carousel(sec, urls, text):
    tok = sec["threads_token"]
    kids = []
    for u in urls:
        k = call("POST", f"{THREADS}/me/threads", media_type="IMAGE", image_url=u, is_carousel_item="true",
                 access_token=tok)["id"]
        _th_wait(tok, k, "carousel image")
        kids.append(k)
    c = _th_create(tok, media_type="CAROUSEL", children=",".join(kids), text=text)
    _th_wait(tok, c, "carousel")
    return call("POST", f"{THREADS}/me/threads_publish", creation_id=c, access_token=tok)["id"]


def post_threads_reply(sec, url, text, reply_to):
    """Reply under our own Threads post with the same image, in the second topic."""
    tok = sec["threads_token"]
    c = call("POST", f"{THREADS}/me/threads", media_type="IMAGE", image_url=url, text=text,
             reply_to_id=reply_to, topic_tag=THREADS_TOPIC_2, access_token=tok)["id"]
    for _ in range(30):
        st = call("GET", f"{THREADS}/{c}", fields="status", access_token=tok).get("status")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads could not process the reply image ({st})")
        time.sleep(5)
    return call("POST", f"{THREADS}/me/threads_publish", creation_id=c, access_token=tok)["id"]


PLATFORMS = ["instagram", "threads"] + (["facebook"] if FACEBOOK_ENABLED else [])


# ---------- commands ----------
def wait_live(url):
    for _ in range(30):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
                if r.status == 200:
                    return
        except urllib.error.URLError:
            pass
        time.sleep(10)
    raise RuntimeError(f"{url} is not online yet")


def is_live(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
            return r.status == 200
    except urllib.error.URLError:
        return False


def mockup_url(w):
    u = f"{SITE}/assets/mockup/{w['slug']}.jpg"
    return u if is_live(u) else None


def reel_url(w):
    u = f"{SITE}/assets/reels/{w['slug']}.mp4"
    return u if is_live(u) else None


def load_series():
    return json.loads(SERIES.read_text()) if SERIES.exists() else []


def share_single(sec, w, done):
    wide = is_wide(w)
    url = image_url(w, wide)
    wait_live(url)
    mock = mockup_url(w) or url        # the wallpaper on a phone / monitor
    reel = None if wide else reel_url(w)  # phone: Instagram Reels video; desktop: monitor mockup photo
    texts = captions(w, wide)
    ok = True
    for p in [p for p in PLATFORMS if p not in done]:
        try:
            if p == "instagram":
                done[p] = post_instagram_reel(sec, reel, texts[p]) if reel else post_instagram(sec, mock, texts[p])
            elif p == "threads":
                done[p] = post_threads(sec, mock, texts[p])
            else:
                done[p] = post_facebook(sec, url, texts[p])
            print(f"{w['slug']}: shared on {p} ({done[p]}){' as reel' if p == 'instagram' and reel else ''}")
        except Exception as e:  # keep going with the other platforms
            ok = False
            print(f"::error::{w['slug']} on {p}: {e}")
    if "threads_4k" not in done and w.get("date", "") >= REPLY_FROM and "threads" in done:
        text = f"Also in {THREADS_TOPIC_2} 🖼️ Free full-res download 👉 wallspotter.com/{w['slug']}"
        try:  # the reply shows the plain full-size wallpaper
            done["threads_4k"] = post_threads_reply(sec, url, text, done["threads"])
            print(f"{w['slug']}: replied on threads in {THREADS_TOPIC_2} ({done['threads_4k']})")
        except Exception as e:
            print(f"::warning::{w['slug']} threads reply: {e}")
    return ok


def share_series(sec, series, items, state):
    """One carousel per platform for the whole series; every slug gets the same post id."""
    urls = []
    for w in items:
        wait_live(image_url(w, is_wide(w)))
        urls.append(mockup_url(w) or image_url(w, is_wide(w)))
    texts = series_captions(series, items)
    first = state.setdefault(items[0]["slug"], {})
    ok = True
    for p, fn in (("instagram", post_instagram_carousel), ("threads", post_threads_carousel)):
        if p in first:
            continue
        try:
            pid = fn(sec, urls, texts[p])
            for w in items:
                state.setdefault(w["slug"], {})[p] = pid
            print(f"series {series['id']}: shared on {p} as a {len(items)}-image carousel ({pid})")
        except Exception as e:
            ok = False
            print(f"::error::series {series['id']} on {p}: {e}")
    for w in items:
        d = state.setdefault(w["slug"], {})
        d["series"] = series["id"]
        d["threads_4k"] = "series"   # no separate 4K reply for series
        if not FACEBOOK_ENABLED:
            d.setdefault("facebook", "off")
    return ok


def cmd_post():
    sec = load_secrets()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    walls = wallpapers()
    by_slug = {w["slug"]: w for w in walls}
    series_list = load_series()
    in_series = {s for sr in series_list for s in sr.get("slugs", [])}
    failed = False
    for w in walls:
        if w["slug"] in in_series:
            continue
        done = state.setdefault(w["slug"], {})
        if not FACEBOOK_ENABLED:
            done.setdefault("facebook", "off")   # never post the backlog when sharing is off
        need_reply = "threads_4k" not in done and w.get("date", "") >= REPLY_FROM
        if all(p in done for p in PLATFORMS) and not need_reply:
            continue
        failed |= not share_single(sec, w, done)
        STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    for sr in series_list:
        items = [by_slug[s] for s in sr.get("slugs", []) if s in by_slug]
        if len(items) != len(sr.get("slugs", [])) or not items:
            continue   # not all images are on the site yet
        if all({"instagram", "threads"} <= set(state.get(w["slug"], {})) for w in items):
            continue
        failed |= not share_series(sec, sr, items, state)
        STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    if failed:
        sys.exit(1)


def cmd_check():
    sec = load_secrets()
    print("Facebook page:", call("GET", f"{GRAPH}/{FB_PAGE_ID}", fields="name", access_token=sec["page_token"])["name"])
    print("Instagram:", call("GET", f"{GRAPH}/{IG_USER_ID}", fields="username", access_token=sec["page_token"])["username"])
    print("Threads:", call("GET", f"{THREADS}/me", fields="username", access_token=sec["threads_token"])["username"])
    print("Threads token last renewed:", sec.get("threads_renewed", "?"))


def cmd_refresh():
    sec = load_secrets()
    r = call("GET", f"{THREADS}/refresh_access_token", grant_type="th_refresh_token", access_token=sec["threads_token"])
    sec["threads_token"] = r["access_token"]
    sec["threads_renewed"] = date.today().isoformat()
    save_secrets(sec)
    print("Threads token renewed; valid for", r.get("expires_in", 0) // 86400, "days")


def _metric(item):
    if "total_value" in item:
        return item["total_value"].get("value", 0)
    vals = item.get("values") or [{}]
    return vals[-1].get("value", 0)


def cmd_stats():
    """Most liked/replied Threads posts of the last 30 days, used as inspiration for new wallpapers."""
    import re
    from datetime import datetime, timedelta, timezone
    sec = load_secrets()
    tok = sec["threads_token"]
    since = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())
    posts, url, params = [], f"{THREADS}/me/threads", dict(fields="id,timestamp,permalink,text,media_type,media_url",
                                                            since=since, limit=100, access_token=tok)
    while url and len(posts) < 500:
        r = call("GET", url, **params)
        posts += r.get("data", [])
        nxt = (r.get("paging") or {}).get("next")
        url, params = (nxt.split("?")[0], dict(urllib.parse.parse_qsl(nxt.split("?", 1)[1]))) if nxt else (None, None)
    rows = []
    for p in posts:
        try:
            ins = call("GET", f"{THREADS}/{p['id']}/insights", metric="views,likes,replies,reposts,quotes", access_token=tok)
            m = {i["name"]: _metric(i) for i in ins.get("data", [])}
        except Exception as e:
            print("::warning::insights failed for", p["id"], e)
            continue
        slug = re.search(r"wallspotter\.com/([a-z0-9-]+)", p.get("text") or "")
        score = m.get("likes", 0) + 2 * m.get("replies", 0) + 2 * m.get("reposts", 0) + 2 * m.get("quotes", 0)
        rows.append({"slug": slug.group(1) if slug else None, "permalink": p.get("permalink"), "date": p.get("timestamp", "")[:10],
                     "score": score, **{k: m.get(k, 0) for k in ("likes", "replies", "reposts", "quotes", "views")},
                     "title": (p.get("text") or "").split("\n")[0][:80]})
    rows.sort(key=lambda r: (r["score"], r["views"]), reverse=True)
    out = {"updated": date.today().isoformat(), "window_days": 30, "posts": rows[:20]}
    (ROOT / "data" / "threads-top.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for r in rows[:5]:
        print(f"{r['score']:>4}  likes={r['likes']} replies={r['replies']} views={r['views']}  {r['slug'] or r['title']}")


def cmd_engagement():
    """Print Instagram and Facebook likes/comments per wallpaper (read only)."""
    import re
    sec = load_secrets(); tok = sec["page_token"]
    rows, url, params = [], f"{GRAPH}/{IG_USER_ID}/media", dict(fields="caption,like_count,comments_count,timestamp", limit=100, access_token=tok)
    while url and len(rows) < 300:
        r = call("GET", url, **params)
        for m in r.get("data", []):
            if m.get("timestamp", "") < "2026-10-01":
                continue
            rows.append(("IG", m.get("like_count", 0), m.get("comments_count", 0), m.get("timestamp", "")[:10], (m.get("caption") or "").split("\n")[0][:60]))
        nxt = (r.get("paging") or {}).get("next")
        url, params = (nxt.split("?")[0], dict(urllib.parse.parse_qsl(nxt.split("?", 1)[1]))) if nxt else (None, None)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    for slug, done in state.items():
        pid = done.get("facebook")
        if not pid or not str(pid)[:1].isdigit():
            continue
        try:
            m = call("GET", f"{GRAPH}/{pid}", fields="created_time,reactions.summary(true).limit(0),comments.summary(true).limit(0)", access_token=tok)
        except RuntimeError as e:
            print("Facebook post not readable:", slug, str(e)[:200]); break
        rows.append(("FB", m.get("reactions", {}).get("summary", {}).get("total_count", 0), m.get("comments", {}).get("summary", {}).get("total_count", 0),
                     m.get("created_time", "")[:10], slug))
    rows.sort(key=lambda x: (x[1] + 2 * x[2]), reverse=True)
    for net in ("IG", "FB"):
        part = [x for x in rows if x[0] == net]
        print(f"== {net}: {len(part)} posts, {sum(x[1] for x in part)} likes/reactions, {sum(x[2] for x in part)} comments")
        for x in part[:20]:
            print(f"{x[0]} likes={x[1]:>3} comments={x[2]:>3} {x[3]}  {x[4]}")


def cmd_unpublish():
    """Delete the social posts of wallpapers that were removed from data/wallpapers.csv."""
    sec = load_secrets()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    with open(ROOT / "data" / "wallpapers.csv", newline="", encoding="utf-8") as f:
        live = {r["slug"] for r in csv.DictReader(f) if r.get("slug")}
    targets = {
        "facebook": (GRAPH, "page_token"), "instagram": (GRAPH, "page_token"),
        "threads_4k": (THREADS, "threads_token"), "threads": (THREADS, "threads_token"),
    }
    for slug in [s for s in state if s not in live]:
        done = state[slug]
        for key in ["facebook", "threads_4k", "threads", "instagram"]:
            pid = done.get(key)
            if not pid or not str(pid).replace("_", "").isdigit():
                continue
            base, tok = targets[key]
            try:
                call("DELETE", f"{base}/{pid}", access_token=sec[tok])
                print(f"{slug}: deleted {key} ({pid})")
                done.pop(key)
            except RuntimeError as e:
                print(f"::warning::{slug}: could not delete {key} ({pid}): {e}")
        if not done:
            state.pop(slug)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def cmd_daily():
    sec = load_secrets()
    last = sec.get("threads_renewed", "2000-01-01")
    if (date.today() - date.fromisoformat(last)).days >= 6:
        cmd_refresh()
    cmd_stats()


if __name__ == "__main__":
    {"post": cmd_post, "check": cmd_check, "refresh": cmd_refresh, "stats": cmd_stats, "daily": cmd_daily, "engagement": cmd_engagement, "unpublish": cmd_unpublish}[sys.argv[1] if len(sys.argv) > 1 else "post"]()
