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


# ---------- daily recap reel ----------
def ambient_track(path, seconds, seed=0, sr=44100):
    """Calm ambient pad (our own, royalty-free): slow chords + soft bell notes + reverb. Writes 16-bit stereo WAV."""
    import wave
    import numpy as np
    rng = np.random.default_rng(seed)
    roots = [57, 55, 53, 52, 50, 48]                     # A3, G3, F3, E3, D3, C3
    root = roots[seed % len(roots)]
    progs = [[0, -4, 3, -2], [0, 5, -3, -5], [0, -3, -7, -5], [0, 3, 5, -2]]
    prog = progs[(seed // len(roots)) % len(progs)]
    shapes = [[0, 7, 10, 14, 15], [0, 7, 11, 14, 16], [0, 4, 7, 11, 14], [0, 3, 7, 10, 14]]
    hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros((n, 2))
    step = max(3.0, seconds / len(prog))
    for i, deg in enumerate(prog * 4):
        start = i * step
        if start >= seconds:
            break
        dur = step + 1.5
        a, b = int(start * sr), min(n, int((start + dur) * sr))
        tt = t[a:b] - start
        env = np.minimum(1, tt / 1.4) * np.clip((dur - tt) / 1.6, 0, 1)
        shape = shapes[(i + seed) % len(shapes)] if deg % 2 else shapes[seed % len(shapes)]
        for k, iv in enumerate(shape):
            f = hz(root + deg + iv)
            for ch, det in ((0, -0.6), (1, 0.6)):
                v = np.sin(2 * np.pi * (f + det) * tt) + 0.25 * np.sin(2 * np.pi * 2 * (f + det) * tt)
                out[a:b, ch] += v * env * (0.11 if k == 0 else 0.06)
    # soft bell notes from the pentatonic scale
    penta = [0, 3, 5, 7, 10, 12, 15]
    for s in np.arange(1.0, seconds - 1.5, 1.6):
        if rng.random() < 0.35:
            continue
        f = hz(root + 24 + penta[rng.integers(len(penta))])
        a = int(s * sr); b = min(n, a + int(2.5 * sr))
        tt = t[a:b] - s
        v = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.2) * 0.07
        pan = rng.random()
        out[a:b, 0] += v * (1 - pan) * 1.4
        out[a:b, 1] += v * pan * 1.4
    # reverb: convolve with a decaying noise tail
    ir_len = int(2.2 * sr)
    ir = rng.standard_normal((ir_len, 2)) * np.exp(-np.arange(ir_len) / sr * 2.6)[:, None] * 0.018
    ir[0] = 1.0
    L = 1 << (n + ir_len).bit_length()
    wet = np.stack([np.fft.irfft(np.fft.rfft(out[:, c], L) * np.fft.rfft(ir[:, c], L), L)[:n] for c in (0, 1)], 1)
    mix = 0.55 * out + 0.45 * wet
    fade = np.minimum(1, np.minimum(t / 1.0, (seconds - t) / 1.5))[:, None]
    mix = mix * np.clip(fade, 0, 1)
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.5
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((mix * 32767).astype("<i2").tobytes())


def _recap_slide(src, wide, number, total, size=(1080, 1920)):
    """One full-screen slide: phone wallpapers fill the screen, desktop ones sit on a monitor."""
    W, H = size
    if wide:
        canvas = _backdrop(src, W, H, 0.5)
        mon = _monitor(src, round(W * 0.92))
        x, y = (W - mon.width) // 2, (H - mon.height) // 2
        _shadow(canvas, (x + 12, y + 30, x + mon.width - 12, y + mon.height), 24, 34)
        canvas.paste(mon, (x, y), mon)
    else:
        canvas = _cover(src, W, H)
    # number badge
    d = ImageDraw.Draw(canvas, "RGBA")
    f = _font(46)
    label = f"{number}/{total}"
    tw = d.textlength(label, font=f)
    d.rounded_rectangle((48, 70, 48 + tw + 44, 70 + 72), radius=36, fill=(0, 0, 0, 120))
    d.text((70, 80), label, font=f, fill=(255, 255, 255, 240))
    return canvas


def _recap_end(first, size=(1080, 1920)):
    W, H = size
    canvas = _backdrop(first, W, H, 0.35)
    d = ImageDraw.Draw(canvas)
    for text, fs, y in (("Which one is your favorite?", 64, H * 0.40), ("Tell me the number 👇".replace(" 👇", ""), 52, H * 0.40 + 100),
                        ("Free downloads", 46, H * 0.58), ("wallspotter.com", 70, H * 0.58 + 70)):
        f = _font(fs)
        tw = d.textlength(text, font=f)
        d.text(((W - tw) / 2, y), text, font=f, fill=(250, 250, 250))
    return canvas


def make_daily_reel(items, dst_path, seed=0, slide=2.2, fade=0.45, end=2.6, fps=30):
    """items: list of (image_path, wide). 1080x1920 video: numbered slides with a slow zoom,
    crossfades, an end card, and our own ambient music."""
    W, H = 1080, 1920
    srcs = []
    for p, wide in items:
        with Image.open(p) as im:
            srcs.append((im.convert("RGB"), wide))
    slides = [_recap_slide(s, wd, i + 1, len(srcs)) for i, (s, wd) in enumerate(srcs)]
    slides.append(_recap_end(srcs[0][0]))
    durs = [slide] * (len(slides) - 1) + [end]
    total = sum(durs) - fade * (len(slides) - 1)
    starts, acc = [], 0.0
    for d in durs:
        starts.append(acc)
        acc += d - fade
    frames = int(total * fps)

    def frame_of(i, t_local):
        im = slides[i]
        z = 1.0 + 0.06 * min(1.0, t_local / durs[i])   # slow zoom-in
        cw, ch = W / z, H / z
        x0, y0 = (W - cw) / 2, (H - ch) / 2
        return im.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "music.wav"
        ambient_track(wav, total + 0.1, seed)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(dst_path)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for k in range(frames):
            t = k / fps
            act = [i for i in range(len(slides)) if starts[i] <= t < starts[i] + durs[i]]
            img = frame_of(act[0], t - starts[act[0]])
            if len(act) > 1:  # crossfade into the next slide
                nxt = act[1]
                a = (t - starts[nxt]) / fade
                img = Image.blend(img, frame_of(nxt, t - starts[nxt]), max(0.0, min(1.0, a)))
            proc.stdin.write(img.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")


def lofi_track(path, seconds, seed=0, sr=44100):
    """Chill lo-fi beat (our own, royalty-free): electric-piano chords, soft drums, bass, vinyl crackle."""
    import wave
    import numpy as np
    rng = np.random.default_rng(seed)
    bpm = [72, 76, 80, 84][seed % 4]
    beat = 60.0 / bpm
    n = int(seconds * sr)
    out = np.zeros((n, 2))
    hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    key = [0, 2, 3, 5, 7, 9][(seed // 4) % 6]
    progs = [  # (root offset, chord intervals) – jazzy 7th/9th chords
        [(2, [0, 3, 7, 10, 14]), (7, [0, 4, 7, 10, 14]), (0, [0, 4, 7, 11, 14]), (9, [0, 3, 7, 10, 14])],
        [(0, [0, 4, 7, 11, 14]), (9, [0, 3, 7, 10, 14]), (5, [0, 4, 7, 11, 14]), (7, [0, 4, 7, 10, 13])],
        [(9, [0, 3, 7, 10, 14]), (5, [0, 4, 7, 11, 14]), (0, [0, 4, 7, 11, 14]), (7, [0, 5, 7, 10, 14])],
    ]
    prog = progs[seed % len(progs)]
    base = 48 + key  # C3 + key

    def add(sig, start, gain=1.0, pan=0.5):
        a = int(start * sr)
        if a >= n:
            return
        b = min(n, a + len(sig))
        out[a:b, 0] += sig[:b - a] * gain * (1 - pan) * 2
        out[a:b, 1] += sig[:b - a] * gain * pan * 2

    def epiano(f, dur):
        t = np.arange(int(dur * sr)) / sr
        s = sum(np.sin(2 * np.pi * f * k * t) * np.exp(-t * (1.2 + 1.8 * k)) / k ** 1.4 for k in range(1, 5))
        s *= np.minimum(1, t / 0.008) * (1 + 0.12 * np.sin(2 * np.pi * 4.5 * t))  # attack + tremolo
        return s

    bar = 4 * beat
    bars = int(seconds / bar) + 1
    for i in range(bars):
        t0 = i * bar
        root, ivs = prog[i % len(prog)]
        # chords: on beat 1 and a softer push on the "and" of 3
        for when, g in ((0, 1.0), (2.5 * beat, 0.55)):
            for j, iv in enumerate(ivs):
                add(epiano(hz(base + root + iv), bar), t0 + when + j * 0.012, 0.075 * g, 0.35 + 0.08 * j)
        # bass
        for when in (0, 1.75 * beat, 2.5 * beat):
            d = 0.9 * beat
            tt = np.arange(int(d * sr)) / sr
            f = hz(base - 12 + root)
            add(np.sin(2 * np.pi * f * tt) * np.exp(-tt * 3) * np.minimum(1, tt / 0.01), t0 + when, 0.22)
        # drums (skip in the first bar as an intro)
        if i == 0:
            continue
        for k in (0, 2.5):          # kick
            tt = np.arange(int(0.4 * sr)) / sr
            ph = 2 * np.pi * np.cumsum(45 + 75 * np.exp(-tt * 30)) / sr
            add(np.sin(ph) * np.exp(-tt * 9), t0 + k * beat, 0.45)
        for k in (1, 3):            # snare / rim
            tt = np.arange(int(0.25 * sr)) / sr
            nz = rng.standard_normal(len(tt))
            nz = nz - np.convolve(nz, np.ones(6) / 6, "same")
            add((nz * 0.6 + np.sin(2 * np.pi * 190 * tt) * 0.4) * np.exp(-tt * 18), t0 + k * beat, 0.16)
        for k in range(8):          # swung hi-hats
            tt = np.arange(int(0.06 * sr)) / sr
            nz = rng.standard_normal(len(tt))
            nz = np.diff(nz, prepend=0)
            when = k * beat / 2 + (0.06 * beat if k % 2 else 0)
            add(nz * np.exp(-tt * 70), t0 + when, 0.035 * (1.0 if k % 2 == 0 else 0.7), 0.6)
    # vinyl crackle + soft noise bed
    crack = np.zeros(n)
    idx = rng.integers(0, n, int(seconds * 9))
    crack[idx] = rng.uniform(-1, 1, len(idx))
    out += (crack * 0.05 + rng.standard_normal(n) * 0.0025)[:, None]
    # warm low-pass (one-pole), gentle tape wobble omitted for simplicity
    alpha = 0.32
    for c in (0, 1):
        x = out[:, c]
        y = np.empty_like(x)
        acc = 0.0
        # vectorised one-pole via lfilter-like recursion in chunks
        from itertools import accumulate
        y = np.fromiter(accumulate(x, lambda p, v: p + alpha * (v - p)), float, len(x))
        out[:, c] = y
    t = np.arange(n) / sr
    fade = np.clip(np.minimum(t / 1.2, (seconds - t) / 2.0), 0, 1)[:, None]
    out *= fade
    out = np.tanh(out / (np.abs(out).max() + 1e-9) * 1.6) * 0.55
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype("<i2").tobytes())


def _cover_frame(src, t_frac, W=1080, H=1920):
    """Full-screen slow horizontal pan across a wide image (t_frac 0..1)."""
    s = H / src.height
    big_w = round(src.width * s)
    x = (big_w - W) * (0.2 + 0.6 * t_frac) / s
    return src.resize((W, H), Image.BICUBIC, box=(x, 0, x + W / s, src.height))


def make_daily_reel(items, dst_path, seed=0, min_seconds=31, fade=0.6, end=3.5, fps=30):
    """items: list of (image_path, wide). A >= min_seconds vertical 1080x1920 video:
    phone wallpapers fill the screen with a slow zoom; desktop wallpapers appear on a monitor,
    then full-screen with a slow pan. Numbered badges, crossfades, an end card and synthwave-techno music (scripts/music.py)."""
    W, H = 1080, 1920
    srcs = []
    for p, wide in items:
        with Image.open(p) as im:
            srcs.append((im.convert("RGB"), wide))
    n = len(srcs)
    # each wallpaper gets the same share of the time; desktop ones split it into two shots
    per = max(3.2, (min_seconds - end + fade * n) / n)
    shots = []   # (kind, image, number, duration)
    for i, (s, wide) in enumerate(srcs):
        if wide:
            shots.append(("still", _recap_slide(s, True, i + 1, n), per * 0.5 + fade / 2))
            shots.append(("pan", (s, i + 1), per * 0.5 + fade / 2))
        else:
            shots.append(("still", _recap_slide(s, False, i + 1, n), per))
    shots.append(("still", _recap_end(srcs[0][0]), end))
    starts, acc = [], 0.0
    for _, _, d in shots:
        starts.append(acc)
        acc += d - fade
    total = acc + fade
    frames = int(total * fps)
    badge_font = _font(46)

    def badge(img, num):
        d = ImageDraw.Draw(img, "RGBA")
        label = f"{num}/{n}"
        tw = d.textlength(label, font=badge_font)
        d.rounded_rectangle((48, 70, 48 + tw + 44, 142), radius=36, fill=(0, 0, 0, 120))
        d.text((70, 80), label, font=badge_font, fill=(255, 255, 255, 240))
        return img

    def frame_of(i, t_local):
        kind, obj, dur = shots[i]
        f = max(0.0, min(1.0, t_local / dur))
        if kind == "pan":
            src, num = obj
            return badge(_cover_frame(src, f), num)
        z = 1.0 + 0.08 * f if i % 2 == 0 else 1.08 - 0.08 * f   # alternate zoom in / out
        cw, ch = W / z, H / z
        x0, y0 = (W - cw) / 2, (H - ch) / 2
        return obj.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "music.wav"
        import music  # scripts/music.py
        music.make_track(wav, total + 0.2, "technowave", seed)  # 2026-11-19: synthwave + techno, 116 BPM
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(dst_path)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for k in range(frames):
            t = k / fps
            act = [i for i in range(len(shots)) if starts[i] <= t < starts[i] + shots[i][2]]
            img = frame_of(act[0], t - starts[act[0]])
            if len(act) > 1:
                nxt = act[1]
                img = Image.blend(img, frame_of(nxt, t - starts[nxt]), max(0.0, min(1.0, (t - starts[nxt]) / fade)))
            proc.stdin.write(img.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")
