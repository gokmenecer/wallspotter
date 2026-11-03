"""Share new WallSpotter wallpapers on Facebook, Instagram and Threads.

Runs in GitHub Actions after the site is deployed (see .github/workflows/social.yml).

  python scripts/social.py post      share every originals wallpaper not yet in data/social-posted.json
  python scripts/social.py check     only test that the saved tokens still work
  python scripts/social.py refresh   renew the Threads token (it lasts 60 days) and save it again

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
def call(method, url, **params):
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url.split('?')[0]} -> {e.code}: {body}") from None


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
    c = call("POST", f"{THREADS}/me/threads", media_type="IMAGE", image_url=url, text=text, access_token=tok)["id"]
    for _ in range(30):
        st = call("GET", f"{THREADS}/{c}", fields="status", access_token=tok).get("status")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads could not process the image ({st})")
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
        if not todo:
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


if __name__ == "__main__":
    {"post": cmd_post, "check": cmd_check, "refresh": cmd_refresh}[sys.argv[1] if len(sys.argv) > 1 else "post"]()
