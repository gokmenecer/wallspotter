"""Royalty-free background music for WallSpotter Reels, synthesised from scratch with numpy.

    make_track(path, seconds, style="house", seed=0)   -> 44.1 kHz stereo 16-bit WAV

Styles: "house" (chill house, 120 BPM), "futurepop" (pumping future-pop, 100 BPM),
"synthwave" (retro driving synthwave, 108 BPM). The seed picks the key and the chord progression.
"""
import wave

import numpy as np
from scipy.signal import butter, lfilter

SR = 44100
PROGRESSIONS = [  # (semitones from the key root, minor?) – four bars
    [(9, True), (5, False), (0, False), (7, False)],    # vi IV I V
    [(0, False), (7, False), (9, True), (5, False)],    # I V vi IV
    [(9, True), (7, False), (5, False), (7, False)],    # vi V IV V
    [(2, True), (7, False), (0, False), (9, True)],     # ii V I vi
]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _t(dur):
    return np.arange(max(1, int(dur * SR))) / SR


def _filt(x, kind, fc, order=2):
    fc = np.atleast_1d(fc) / (SR / 2)
    b, a = butter(order, fc if len(fc) > 1 else fc[0], btype=kind)
    return lfilter(b, a, x)


def _saw(f, dur, detune=0.0, max_h=28):
    t = _t(dur)
    out = np.zeros_like(t)
    ph = np.random.uniform(0, 2 * np.pi)
    for k in range(1, max_h + 1):
        if f * k > 14000:
            break
        out += np.sin(2 * np.pi * (f + detune) * k * t + ph * k) / k
    return out * 0.6


def _square(f, dur, max_h=15):
    t = _t(dur)
    out = np.zeros_like(t)
    for k in range(1, max_h + 1, 2):
        if f * k > 12000:
            break
        out += np.sin(2 * np.pi * f * k * t) / k
    return out * 0.7


def _env(dur, a=0.005, d=0.1, s=0.6, r=0.05):
    t = _t(dur)
    e = np.where(t < a, t / max(a, 1e-6), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-6)))
    rel = np.clip((dur - t) / max(r, 1e-6), 0, 1)
    return e * rel


def _kick(dur=0.45, punch=1.0):
    t = _t(dur)
    f = 45 + 110 * np.exp(-t * 28)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    click = np.random.randn(len(t)) * np.exp(-t * 400) * 0.3 * punch
    return np.tanh((body + click) * 1.1)


def _noise(dur):
    return np.random.randn(len(_t(dur)))


def _clap():
    out = np.zeros(len(_t(0.35)))
    for off in (0, 0.011, 0.023):
        n = _filt(_noise(0.3), "band", [900, 2600]) * np.exp(-_t(0.3) * 22)
        a = int(off * SR)
        out[a:a + len(n)] += n[:len(out) - a]
    return out * 0.9


def _snare(dur=0.3):
    t = _t(dur)
    nz = _filt(_noise(dur), "band", [1500, 7000]) * np.exp(-t * 16)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 25)
    return nz * 0.9 + tone * 0.6


def _hat(open_=False):
    dur = 0.28 if open_ else 0.05
    t = _t(dur)
    return _filt(_noise(dur), "high", 7500) * np.exp(-t * (9 if open_ else 80))


def _reverb(x, secs=1.6, mix=0.25, seed=0):
    rng = np.random.default_rng(seed + 7)
    n = int(secs * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * (4.5 / secs)) * 0.02
    ir[0] = 1.0
    L = 1 << (len(x) + n).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[:len(x)]
    return x * (1 - mix) + wet * mix


class _Mix:
    def __init__(self, seconds):
        self.n = int(seconds * SR)
        self.bus = {k: np.zeros((self.n, 2)) for k in ("drums", "music", "fx")}

    def add(self, bus, sig, start, gain=1.0, pan=0.5):
        a = int(start * SR)
        if a >= self.n or a < 0:
            return
        b = min(self.n, a + len(sig))
        s = sig[:b - a] * gain
        self.bus[bus][a:b, 0] += s * (1 - pan) * 2 ** 0.5
        self.bus[bus][a:b, 1] += s * pan * 2 ** 0.5


def _chord(root, minor, extra=(10, 14)):
    third = 3 if minor else 4
    return [root, root + third, root + 7] + [root + e for e in extra if (minor or e != 10) or True][:1]


def make_track(path, seconds, style="house", seed=0):
    np.random.seed(seed)
    key = [0, 2, 5, 7, 9, 10][seed % 6]
    prog = PROGRESSIONS[(seed // 6) % len(PROGRESSIONS)]
    bpm = {"house": 120, "futurepop": 100, "synthwave": 108}[style]
    beat = 60 / bpm
    bar = 4 * beat
    mix = _Mix(seconds)
    kicks = []
    bars = int(seconds / bar) + 1
    base = 48 + key  # C3 + key

    for i in range(bars):
        t0 = i * bar
        root_off, minor = prog[i % 4]
        root = base + root_off
        notes = _chord(root, minor)
        intro = i == 0
        if style == "house":
            # drums: four-on-the-floor, clap 2&4, off-beat open hat, soft 16th hats
            for b in range(4):
                if not intro:
                    mix.add("drums", _kick(), t0 + b * beat, 0.9); kicks.append(t0 + b * beat)
                    mix.add("drums", _hat(True), t0 + b * beat + beat / 2, 0.1, 0.6)
                for s in range(4):
                    mix.add("drums", _hat(), t0 + b * beat + s * beat / 4, 0.03 if s % 2 else 0.05, 0.4)
            if not intro:
                for b in (1, 3):
                    mix.add("drums", _clap(), t0 + b * beat, 0.45, 0.5)
            # off-beat chord stabs + pad
            for st in (0.5, 1.5, 2.5, 3.0, 3.5):
                stab = sum(_saw(hz(m + 12), 0.22) for m in notes) * _env(0.22, 0.004, 0.09, 0.0, 0.03)
                mix.add("music", _filt(stab, "low", 2600), t0 + st * beat, 0.16, 0.45)
            pad = sum(_saw(hz(m + 12), bar, detune=0.4) + _saw(hz(m + 12), bar, detune=-0.4) for m in notes)
            mix.add("music", _filt(pad, "low", 1400) * _env(bar, 0.3, 1.0, 0.8, 0.3), t0, 0.035)
            # bass: off-beat
            for b in range(4):
                bs = np.sin(2 * np.pi * hz(root - 12) * _t(beat * 0.45)) * _env(beat * 0.45, 0.004, 0.2, 0.7, 0.04)
                mix.add("music", bs, t0 + b * beat + beat / 2, 0.42)
        elif style == "futurepop":
            # half-time feel: kick 1 & 2.75 (and 3.5 every other bar), big snare on 3
            if not intro:
                for k in ([0, 1.75, 2.5] if i % 2 else [0, 1.75]):
                    mix.add("drums", _kick(0.5, 1.2), t0 + k * beat, 0.95); kicks.append(t0 + k * beat)
                mix.add("drums", _reverb(_snare(0.4), 1.2, 0.35, seed), t0 + 2 * beat, 0.6)
                mix.add("drums", _clap(), t0 + 2 * beat, 0.3)
            for s in range(8):
                mix.add("drums", _hat(), t0 + s * beat / 2, 0.09, 0.6)
            if i % 2 and not intro:  # hat roll at the end of every other bar
                for s in range(6):
                    mix.add("drums", _hat(), t0 + 3 * beat + s * beat / 6, 0.05 + 0.01 * s, 0.6)
            # supersaw chords held for the bar (pumped by the sidechain below)
            ss = np.zeros(len(_t(bar)))
            for m in notes:
                for d in (-0.9, 0, 0.9):
                    ss += _saw(hz(m + 12), bar, detune=d, max_h=20)
            mix.add("music", _filt(ss, "low", 3800) * _env(bar, 0.01, 0.6, 0.85, 0.08), t0, 0.06)
            # pluck arpeggio, 16ths
            arp = [notes[j % len(notes)] + 24 + (12 if j % 8 >= 6 else 0) for j in range(16)]
            for j, m in enumerate(arp):
                pl = _saw(hz(m), 0.18, max_h=10) * np.exp(-_t(0.18) * 22)
                mix.add("music", _filt(pl, "low", 5000), t0 + j * beat / 4, 0.09, 0.3 + 0.4 * (j % 2))
            bs = _saw(hz(root - 12), bar, max_h=6)
            mix.add("music", _filt(bs, "low", 500) * _env(bar, 0.01, 0.4, 0.9, 0.1), t0, 0.22)
        else:  # synthwave
            if not intro:
                for k in (0, 2):
                    mix.add("drums", _kick(0.5), t0 + k * beat, 0.9); kicks.append(t0 + k * beat)
                for k in (1, 3):
                    mix.add("drums", _reverb(_snare(0.5), 1.8, 0.45, seed), t0 + k * beat, 0.55)
            for s in range(8):
                mix.add("drums", _hat(), t0 + s * beat / 2, 0.08 if s % 2 else 0.05, 0.55)
            # driving 8th-note bass
            for s in range(8):
                bs = _filt(_saw(hz(root - 12), beat / 2 * 0.9, max_h=12), "low", 900) * _env(beat / 2 * 0.9, 0.003, 0.12, 0.5, 0.02)
                mix.add("music", bs, t0 + s * beat / 2, 0.3)
            # warm pad
            pad = sum(_saw(hz(m + 12), bar, detune=0.5) + _saw(hz(m + 12), bar, detune=-0.5) for m in notes)
            mix.add("music", _filt(pad, "low", 1800) * _env(bar, 0.25, 1.2, 0.8, 0.25), t0, 0.04)
            # square-wave arpeggio (up-down), 16ths
            seq = notes + notes[-2:0:-1]
            for j in range(16):
                m = seq[j % len(seq)] + 24
                ar = _square(hz(m), beat / 4 * 0.9) * _env(beat / 4 * 0.9, 0.002, 0.06, 0.3, 0.02)
                mix.add("music", _filt(ar, "low", 4200), t0 + j * beat / 4, 0.05, 0.25 + 0.5 * (j % 2))

    # sidechain: duck the music under each kick (strong for future pop)
    depth = {"house": 0.55, "futurepop": 0.8, "synthwave": 0.35}[style]
    sc = np.ones(mix.n)
    t_rel = np.arange(int(0.35 * SR)) / SR
    curve = 1 - depth * np.exp(-t_rel * 9)
    for k in kicks:
        a = int(k * SR)
        b = min(mix.n, a + len(curve))
        sc[a:b] = np.minimum(sc[a:b], curve[:b - a])
    music = mix.bus["music"] * sc[:, None]
    music[:, 0] = _reverb(music[:, 0], 1.4, 0.18, seed)
    music[:, 1] = _reverb(music[:, 1], 1.4, 0.18, seed + 1)
    out = mix.bus["drums"] * 0.9 + music
    t = np.arange(mix.n) / SR
    fade = np.clip(np.minimum(t / 0.4, (seconds - t) / 2.0), 0, 1)[:, None]
    out = out * fade
    out = np.tanh(out / (np.abs(out).max() + 1e-9) * 1.15) * 0.75   # gentle glue/limit
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype("<i2").tobytes())
