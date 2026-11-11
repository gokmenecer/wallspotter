"""Share new WallSpotter wallpapers on Facebook, Instagram and Threads.

Runs in GitHub Actions after the site is deployed (see .github/workflows/social.yml).

  python scripts/social.py post      share every originals wallpaper not yet in data/social-posted.json
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
HASHTAGS = "#wallpaper #phonewallpaper #lockscreen #aiart #wallspotter"
DESKTOP_TAGS = "#wallpaper #desktopwallpaper #4kwallpaper #aiart #wallspotter"
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
    if method == "GET":
        req = urllib.request.Request(endpoint + "?" + data.decode())
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


def captions(w, wide):
    title, desc, link = w["title"], w["description"], f"wallspotter.com/{w['slug']}"
    tags = DESKTOP_TAGS if wide else HASHTAGS
    fb = f"{title} ✨\n\n{desc}\n\nFree full-resolution download 👉 {SITE}/{w['slug']}/"
    ig = f"{title} ✨\n\n{desc}\n\nFree full-resolution download at wallspotter.com (link in bio) 🖼️\n\n{tags}"
    tail = f"\n\nFree full-res download 👉 {link}"
    th = f"{title} ✨\n\n" + short(desc, 500 - len(title) - len(tail) - 6) + tail
    return fb, ig, th


# ---------- platforms ----------
def post_facebook(sec, url, text):
    r = call("POST", f"{GRAPH}/{FB_PAGE_ID}/photos", url=url, message=text, access_token=sec["page_token"])
    return r.get("post_id") or r["id"]


def post_instagram(sec, url, text):
    tok = sec["page_token"]
    c = call("POST", f"{GRAPH}/{IG_USER_ID}/media", image_url=url, caption=text, access_token=tok)["id"]
    for _ in range(30):
        st = call("GET", f"{GRAPH}/{c}", fields="status_code", access_token=tok).get("status_code")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise RuntimeError("Instagram could not process the image")
        time.sleep(5)
    return call("POST", f"{GRAPH}/{IG_USER_ID}/media_publish", creation_id=c, access_token=tok)["id"]


def post_threads(sec, url, text):
    tok = sec["threads_token"]
    try:  # put the post in the "Wallpaper" topic
        c = call("POST", f"{THREADS}/me/threads", media_type="IMAGE", image_url=url, text=text,
                 topic_tag=THREADS_TOPIC, access_token=tok)["id"]
    except RuntimeError as e:
        print(f"::warning::Threads topic tag not accepted, posting without it: {e}")
        c = call("POST", f"{THREADS}/me/threads", media_type="IMAGE", image_url=url, text=text, access_token=tok)["id"]
    for _ in range(30):
        st = call("GET", f"{THREADS}/{c}", fields="status", access_token=tok).get("status")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads could not process the image ({st})")
        time.sleep(5)
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


PLATFORMS = {"facebook": post_facebook, "instagram": post_instagram, "threads": post_threads}


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


def cmd_post():
    sec = load_secrets()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    failed = False
    for w in wallpapers():
        done = state.setdefault(w["slug"], {})
        todo = [p for p in PLATFORMS if p not in done]
        need_reply = "threads_4k" not in done and w.get("date", "") >= REPLY_FROM
        if not todo and not need_reply:
            continue
        wide = is_wide(w)
        url = image_url(w, wide)
        wait_live(url)
        texts = dict(zip(PLATFORMS, captions(w, wide)))
        for p in todo:
            try:
                done[p] = PLATFORMS[p](sec, url, texts[p])
                print(f"{w['slug']}: shared on {p} ({done[p]})")
            except Exception as e:  # keep going with the other platforms
                failed = True
                print(f"::error::{w['slug']} on {p}: {e}")
        if need_reply and "threads" in done:
            wide = is_wide(w)
            url = image_url(w, wide)
            text = f"Also in {THREADS_TOPIC_2} 🖼️ Free full-res download 👉 wallspotter.com/{w['slug']}"
            try:
                done["threads_4k"] = post_threads_reply(sec, url, text, done["threads"])
                print(f"{w['slug']}: replied on threads in {THREADS_TOPIC_2} ({done['threads_4k']})")
            except Exception as e:
                print(f"::warning::{w['slug']} threads reply: {e}")
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
            rows.append(("IG", m.get("like_count", 0), m.get("comments_count", 0), m.get("timestamp", "")[:10], (m.get("caption") or "").split("\n")[0][:60]))
        nxt = (r.get("paging") or {}).get("next")
        url, params = (nxt.split("?")[0], dict(urllib.parse.parse_qsl(nxt.split("?", 1)[1]))) if nxt else (None, None)
    r = call("GET", f"{GRAPH}/{FB_PAGE_ID}/posts", fields="message,created_time,reactions.summary(true),comments.summary(true)", limit=100, access_token=tok)
    for m in r.get("data", []):
        rows.append(("FB", m.get("reactions", {}).get("summary", {}).get("total_count", 0), m.get("comments", {}).get("summary", {}).get("total_count", 0),
                     m.get("created_time", "")[:10], (m.get("message") or "").split("\n")[0][:60]))
    rows.sort(key=lambda x: (x[1] + 2 * x[2]), reverse=True)
    for x in rows[:25]:
        print(f"{x[0]} likes={x[1]:>3} comments={x[2]:>3} {x[3]}  {x[4]}")


def cmd_daily():
    sec = load_secrets()
    last = sec.get("threads_renewed", "2000-01-01")
    if (date.today() - date.fromisoformat(last)).days >= 6:
        cmd_refresh()
    cmd_stats()


if __name__ == "__main__":
    {"post": cmd_post, "check": cmd_check, "refresh": cmd_refresh, "stats": cmd_stats, "daily": cmd_daily, "engagement": cmd_engagement}[sys.argv[1] if len(sys.argv) > 1 else "post"]()
