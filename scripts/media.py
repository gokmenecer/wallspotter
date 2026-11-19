"""Social media images and videos for WallSpotter.

- phone_mockup / desktop_mockup: the wallpaper shown on a plain, brandless phone or
  monitor over a blurred copy of itself (used for Threads and Instagram posts).
- make_reel: a 7-second 1080x1920 vertical video for Instagram Reels
  (phone wallpapers: slow zoom-out from the screen to the whole phone;
  desktop wallpapers: a slow pan across the image). Needs ffmpeg.
"""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FONT_PATHS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _font(size):
    for fp in FONT_PATHS:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _cover(im, w, h):
    """Resize and center-crop to exactly w x h."""
    W, H = im.size
    s = max(w / W, h / H)
    im = im.resize((max(w, round(W * s)), max(h, round(H * s))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def _backdrop(src, w, h, dark=0.42):
    bg = _cover(src, w // 4, h // 4).filter(ImageFilter.GaussianBlur(10)).resize((w, h), Image.BICUBIC)
    return ImageEnhance.Brightness(bg).enhance(dark)


def _shadow(canvas, box, radius, blur, strength=190):
    m = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=radius, fill=strength)
    canvas.paste((0, 0, 0), (0, 0), m.filter(ImageFilter.GaussianBlur(blur)))


def _label(canvas, y, text="wallspotter.com", size=None):
    size = size or max(22, canvas.width // 36)
    f = _font(size)
    d = ImageDraw.Draw(canvas)
    tw = d.textlength(text, font=f)
    d.text(((canvas.width - tw) / 2, y), text, font=f, fill=(245, 245, 245))


def _phone(src, screen_h):
    """A plain dark phone (RGBA) with the wallpaper on its screen."""
    sw = round(screen_h * 0.45)
    bez = max(8, round(screen_h * 0.016))
    pw, ph = sw + 2 * bez, screen_h + 2 * bez
    r_out = round(pw * 0.13)
    r_in = r_out - bez
    side = max(3, bez // 3)  # room for side buttons
    im = Image.new("RGBA", (pw + 2 * side, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # side buttons
    btn = (40, 40, 44, 255)
    d.rounded_rectangle((pw + side - 2, round(ph * 0.24), pw + 2 * side, round(ph * 0.33)), radius=side, fill=btn)
    d.rounded_rectangle((0, round(ph * 0.20), side + 2, round(ph * 0.26)), radius=side, fill=btn)
    d.rounded_rectangle((0, round(ph * 0.28), side + 2, round(ph * 0.34)), radius=side, fill=btn)
    # body with a thin lighter rim
    d.rounded_rectangle((side, 0, side + pw - 1, ph - 1), radius=r_out, fill=(74, 74, 80, 255))
    d.rounded_rectangle((side + 3, 3, side + pw - 4, ph - 4), radius=r_out - 3, fill=(14, 14, 16, 255))
    # screen
    screen = _cover(src, sw, screen_h).convert("RGBA")
    gloss = Image.new("L", (sw, screen_h), 0)
    gd = ImageDraw.Draw(gloss)
    for i in range(screen_h // 2):  # faint glass reflection, strongest at the top-left
        gd.line((0, i, sw - i * sw // screen_h, i), fill=max(0, 22 - i * 44 // screen_h))
    screen = Image.composite(Image.new("RGBA", screen.size, (255, 255, 255, 255)), screen, gloss)
    mask = Image.new("L", (sw, screen_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw - 1, screen_h - 1), radius=r_in, fill=255)
    im.paste(screen, (side + bez, bez), mask)
    # front camera
    cr = max(5, round(sw * 0.022))
    cx, cy = side + pw // 2, bez + round(screen_h * 0.022) + cr
    d.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=(6, 6, 8, 255))
    d.ellipse((cx - cr // 3, cy - cr // 3, cx, cy), fill=(40, 44, 60, 255))
    return im


def phone_mockup(src_path, dst_path, size=(1080, 1350)):
    with Image.open(src_path) as im:
        src = im.convert("RGB")
    W, H = size
    canvas = _backdrop(src, W, H)
    phone = _phone(src, round(H * 0.84))
    x, y = (W - phone.width) // 2, round(H * 0.035)
    _shadow(canvas, (x + 10, y + 24, x + phone.width - 10, y + phone.height + 10), phone.width // 8, 30)
    canvas.paste(phone, (x, y), phone)
    _label(canvas, y + phone.height + round(H * 0.022))
    canvas.save(dst_path, "JPEG", quality=90, optimize=True)


def _monitor(src, screen_w):
    """A plain dark monitor on a stand (RGBA) with the wallpaper on its screen."""
    sh = round(screen_w * 9 / 16)
    bez = max(6, round(screen_w * 0.014))
    chin = bez * 2
    mw, mh = screen_w + 2 * bez, sh + bez + chin
    neck_h, base_h = round(sh * 0.16), max(8, round(sh * 0.035))
    im = Image.new("RGBA", (mw, mh + neck_h + base_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # stand
    nw = round(mw * 0.10)
    d.polygon([(mw // 2 - nw // 2, mh - 2), (mw // 2 + nw // 2, mh - 2),
               (mw // 2 + nw // 3, mh + neck_h), (mw // 2 - nw // 3, mh + neck_h)], fill=(52, 52, 56, 255))
    bw = round(mw * 0.30)
    d.rounded_rectangle((mw // 2 - bw // 2, mh + neck_h - 2, mw // 2 + bw // 2, mh + neck_h + base_h),
                        radius=base_h // 2, fill=(64, 64, 70, 255))
    # body
    d.rounded_rectangle((0, 0, mw - 1, mh - 1), radius=bez * 2, fill=(70, 70, 76, 255))
    d.rounded_rectangle((2, 2, mw - 3, mh - 3), radius=bez * 2, fill=(14, 14, 16, 255))
    im.paste(_cover(src, screen_w, sh), (bez, bez))
    return im


def desktop_mockup(src_path, dst_path, size=(1080, 1080)):
    with Image.open(src_path) as im:
        src = im.convert("RGB")
    W, H = size
    canvas = _backdrop(src, W, H)
    mon = _monitor(src, round(W * 0.86))
    x, y = (W - mon.width) // 2, (H - mon.height) // 2 - round(H * 0.03)
    _shadow(canvas, (x + 12, y + 30, x + mon.width - 12, y + mon.height), 24, 34)
    canvas.paste(mon, (x, y), mon)
    _label(canvas, y + mon.height + round(H * 0.035))
    canvas.save(dst_path, "JPEG", quality=90, optimize=True)


def _ffmpeg(args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def make_reel(src_path, dst_path, wide, seconds=7, fps=30):
    """Vertical 1080x1920 H.264 video with a silent audio track."""
    with Image.open(src_path) as im:
        src = im.convert("RGB")
    frames = seconds * fps
    audio = ["-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(fps),
           "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart"]
    with tempfile.TemporaryDirectory() as tmp:
        still = Path(tmp) / "still.png"
        if wide:
            # pan across the wallpaper, label baked into a strip at the bottom
            H = 1920
            img = src.resize((round(src.width * H / src.height), H), Image.LANCZOS)
            img = img.crop((0, 0, max(img.width, 1081), H))
            img.save(still)
            label = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            grad = Image.new("L", (1080, 260), 0)
            for i in range(260):
                ImageDraw.Draw(grad).line((0, i, 1079, i), fill=i * 150 // 260)
            label.paste((0, 0, 0, 255), (0, 1660), grad)
            _label(label, 1790, "Free 4K download · wallspotter.com", 40)
            lab = Path(tmp) / "label.png"
            label.save(lab)
            travel = img.width - 1080
            # pan over the middle 70% of the image so the subject is in view
            vf = (f"[0:v]crop=1080:1920:x='{travel}*(0.15+0.7*t/{seconds})':y=0,fade=t=in:st=0:d=0.6[v];"
                  f"[v][1:v]overlay=0:0,format=yuv420p[out]")
            _ffmpeg(["-loop", "1", "-framerate", str(fps), "-t", str(seconds), "-i", str(still),
                     "-loop", "1", "-framerate", str(fps), "-t", str(seconds), "-i", str(lab), *audio,
                     "-filter_complex", vf, "-map", "[out]", "-map", "2:a", *enc, str(dst_path)])
        else:
            # big phone on a blurred backdrop, rendered at 2x, slow zoom-out from the screen
            W, H = 2160, 3840
            canvas = _backdrop(src, W, H)
            phone = _phone(src, round(H * 0.80))
            x, y = (W - phone.width) // 2, round(H * 0.06)
            _shadow(canvas, (x + 20, y + 50, x + phone.width - 20, y + phone.height + 20), phone.width // 8, 60)
            canvas.paste(phone, (x, y), phone)
            _label(canvas, y + phone.height + 70, "Free download · wallspotter.com", 76)
            canvas.save(still)
            cy = (y + phone.height // 2) / H
            vf = (f"[0:v]zoompan=z='1.32-0.32*on/{frames - 1}':d={frames}:s=1080x1920:fps={fps}"
                  f":x='iw/2-(iw/zoom/2)':y='ih*{cy:.4f}-(ih/zoom/2)',fade=t=in:st=0:d=0.6,format=yuv420p[out]")
            _ffmpeg(["-loop", "1", "-framerate", str(fps), "-t", str(seconds), "-i", str(still), *audio,
                     "-filter_complex", vf, "-map", "[out]", "-map", "1:a", *enc, str(dst_path)])
