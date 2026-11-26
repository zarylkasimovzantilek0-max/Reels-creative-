"""Procedural SFX library for reels: whooshes, clicks, pops, impacts, risers, dings.

Every sound is synthesized from scratch (no samples, no licensing issues) and written
as a 48 kHz stereo WAV.  sfx/index.json stores each sound's "hit" point in seconds:
the moment that should land exactly on the cut / zoom / text pop.

Usage:  python3 tools/sfx_synth.py sfx/
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- helpers
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def noise(dur):
    return rng.standard_normal(int(dur * SR))


def filt(x, kind, freq, order=2):
    sos = butter(order, freq, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x)


def svf_bandpass(x, fc, q=1.2):
    """Time-varying state-variable band-pass; fc is an array (Hz) per sample."""
    out = np.empty_like(x)
    low = band = 0.0
    damp = 1.0 / q
    f = 2 * np.sin(np.pi * np.clip(fc, 20, SR / 6) / SR)
    for i in range(len(x)):
        high = x[i] - low - damp * band
        band += f[i] * high
        low += f[i] * band
        out[i] = band
    return out


def env_ar(n, attack_frac, curve_a=2.0, curve_r=2.0):
    """Asymmetric swell: rises to 1 at attack_frac, then falls to 0."""
    k = max(1, int(n * attack_frac))
    a = np.linspace(0, 1, k) ** curve_a
    r = np.linspace(1, 0, n - k) ** curve_r
    return np.concatenate([a, r])


def exp_decay(dur, tau):
    return np.exp(-t_axis(dur) / tau)


def reverb(x, size=0.6, mix=0.25, damp=4000):
    ir_t = t_axis(size)
    ir = noise(size) * np.exp(-ir_t / (size / 5))
    ir = filt(ir, "low", damp)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    wet = fftconvolve(x, ir)[: len(x) + int(size * SR)]
    dry = np.concatenate([x, np.zeros(len(wet) - len(x))])
    return dry * (1 - mix) + wet * mix


def stereo(x, pan=None, width=0.0):
    """pan: scalar or per-sample array in [-1, 1]. width: tiny Haas delay in ms."""
    if pan is None:
        pan = 0.0
    pan = np.broadcast_to(pan, x.shape)
    l = x * np.cos((pan + 1) * np.pi / 4)
    r = x * np.sin((pan + 1) * np.pi / 4)
    if width:
        d = int(width / 1000 * SR)
        r = np.concatenate([np.zeros(d), r[:-d]]) * 0.9 + r * 0.1
    return np.stack([l, r], 1) * np.sqrt(2)


def norm(x, peak=0.89):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


# ---------------------------------------------------------------- sounds
def whoosh(dur=0.45, f0=250, f1=3200, f2=700, attack=0.62, pan=(-0.6, 0.6), q=1.4, air=0.25):
    n = int(dur * SR)
    k = int(n * attack)
    fc = np.concatenate([np.geomspace(f0, f1, k), np.geomspace(f1, f2, n - k)])
    x = svf_bandpass(noise(dur), fc, q)
    x += air * filt(noise(dur), "high", 5000) * 0.3
    x *= env_ar(n, attack, 2.2, 1.6)
    p = np.linspace(pan[0], pan[1], n)
    return norm(stereo(x, p, width=6)), dur * attack


def whip(dur=0.2):
    x, hit = whoosh(dur, 900, 7000, 2500, attack=0.45, pan=(0.3, -0.3), q=2.0, air=0.6)
    return x, hit


def reverse_whoosh(dur=0.55):
    n = int(dur * SR)
    fc = np.geomspace(300, 5000, n)
    x = svf_bandpass(noise(dur), fc, 1.3)
    x *= np.linspace(0, 1, n) ** 3
    x[-int(0.008 * SR):] *= np.linspace(1, 0, int(0.008 * SR))
    return norm(stereo(x, np.linspace(-0.4, 0.4, n), width=8)), dur


def click(dur=0.06):
    t = t_axis(dur)
    tick = filt(noise(dur), "high", 2500) * np.exp(-t / 0.0025)
    body = np.sin(2 * np.pi * 3600 * t) * np.exp(-t / 0.006) * 0.6
    low = np.sin(2 * np.pi * 1100 * t) * np.exp(-t / 0.01) * 0.35
    return norm(stereo(tick + body + low, 0.05)), 0.0


def pop(dur=0.14):
    t = t_axis(dur)
    f = 260 + 900 * np.exp(-t / 0.018)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t / 0.035)
    x += filt(noise(dur), "high", 3000) * np.exp(-t / 0.002) * 0.4
    return norm(stereo(x, 0.0)), 0.0


def shutter(dur=0.22):
    t = t_axis(dur)
    def clk(at, amp):
        y = np.zeros_like(t)
        m = t >= at
        tt = t[m] - at
        y[m] = (filt(noise(dur), "band", [1500, 7000])[: m.sum()] * np.exp(-tt / 0.006)
                + np.sin(2 * np.pi * 900 * tt) * np.exp(-tt / 0.012) * 0.4) * amp
        return y
    x = clk(0.0, 1.0) + clk(0.075, 0.7)
    return norm(stereo(x, 0.0, width=4)), 0.0


def impact_boom(dur=1.8):
    t = t_axis(dur)
    f = 36 + 70 * np.exp(-t / 0.07)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.55)
    crack = filt(noise(dur), "low", 2500) * np.exp(-t / 0.035) * 0.9
    tail = filt(noise(dur), "band", [80, 600]) * np.exp(-t / 0.35) * 0.25
    x = np.tanh(1.8 * (sub + crack + tail))
    x = reverb(x, 1.0, 0.18, 2500)
    return norm(stereo(x, 0.0, width=10)), 0.0


def hit(dur=0.9):
    t = t_axis(dur)
    f = 55 + 120 * np.exp(-t / 0.04)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)
    snap = filt(noise(dur), "band", [800, 6000]) * np.exp(-t / 0.05) * 0.7
    x = np.tanh(1.5 * (body + snap))
    x = reverb(x, 0.7, 0.2, 5000)
    return norm(stereo(x, 0.0, width=8)), 0.0


def thump(dur=0.6):
    t = t_axis(dur)
    f = 45 + 60 * np.exp(-t / 0.05)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.18)
    return norm(stereo(np.tanh(1.3 * x), 0.0)), 0.0


def riser(dur=1.3):
    n = int(dur * SR)
    t = t_axis(dur)
    fc = np.geomspace(400, 7000, n)
    nz = svf_bandpass(noise(dur), fc, 2.0)
    tone_f = np.geomspace(180, 1400, n)
    tone = np.sin(2 * np.pi * np.cumsum(tone_f) / SR) * 0.35
    tone += np.sin(2 * np.pi * np.cumsum(tone_f * 1.5) / SR) * 0.15
    x = (nz + tone) * (np.linspace(0, 1, n) ** 2.5)
    # tremolo that speeds up
    x *= 0.75 + 0.25 * np.sin(2 * np.pi * np.cumsum(np.geomspace(4, 22, n)) / SR)
    x[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return norm(stereo(x, np.sin(t * 9) * 0.3, width=8)), dur


def shimmer(dur=0.7):
    t = t_axis(dur)
    x = filt(noise(dur), "high", 6000) * env_ar(len(t), 0.35, 1.5, 2.5) * 0.5
    for _ in range(18):
        at = rng.uniform(0.0, dur * 0.6)
        fr = rng.uniform(3000, 9000)
        m = t >= at
        tt = t[m] - at
        x[m] += np.sin(2 * np.pi * fr * tt) * np.exp(-tt / 0.06) * rng.uniform(0.1, 0.3)
    x = reverb(x, 0.6, 0.35, 9000)
    return norm(stereo(x, np.linspace(-0.7, 0.7, len(x)), width=12)), dur * 0.3


def ding(dur=1.6):
    t = t_axis(dur)
    def bell(f, at, amp):
        y = np.zeros_like(t)
        m = t >= at
        tt = t[m] - at
        mod = np.sin(2 * np.pi * f * 3.5 * tt) * 2.2 * np.exp(-tt / 0.15)
        y[m] = np.sin(2 * np.pi * f * tt + mod) * np.exp(-tt / 0.45) * amp
        return y
    x = bell(1318.5, 0.0, 1.0) + bell(1975.5, 0.09, 0.8)
    x = reverb(x, 0.9, 0.3, 8000)
    return norm(stereo(x, 0.1, width=10)), 0.0


def whoosh_variants():
    return {
        "whoosh": lambda: whoosh(0.42),
        "whoosh_long": lambda: whoosh(0.65, 180, 2600, 500, attack=0.55, pan=(-0.8, 0.8)),
        "whoosh_out": lambda: _hit_at_start(whoosh(0.5, 2800, 3500, 300, attack=0.08, pan=(0.0, 0.0), q=1.1)),
        "whoosh_out_soft": lambda: whoosh(0.8, 200, 1800, 300, attack=0.5, pan=(0.6, -0.6), q=1.0, air=0.1),
        "whoosh_down": lambda: whoosh(0.55, 3500, 1200, 180, attack=0.3, pan=(0.5, -0.5), q=1.2),
        "whoosh_up": lambda: whoosh(0.5, 180, 1200, 4200, attack=0.75, pan=(-0.5, 0.5), q=1.2),
        "whoosh_blur": lambda: _blur_whoosh(),
    }


def _hit_at_start(pair):
    x, _ = pair
    return x, 0.0


def _blur_whoosh(dur=0.75):
    x, hit = whoosh(dur, 120, 1400, 200, attack=0.55, pan=(-0.3, 0.3), q=0.9, air=0.05)
    t = t_axis(dur)
    sub = np.sin(2 * np.pi * 50 * t) * env_ar(len(t), 0.55, 2, 2) * 0.5
    x[: len(sub)] += stereo(sub)[: len(x)]
    return norm(x), hit


SOUNDS = {
    "whip": whip,
    "reverse_whoosh": reverse_whoosh,
    "click": click,
    "pop": pop,
    "shutter": shutter,
    "impact_boom": impact_boom,
    "hit": hit,
    "thump": thump,
    "riser": riser,
    "shimmer": shimmer,
    "ding": ding,
    **whoosh_variants(),
}


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    index = {}
    for name, fn in SOUNDS.items():
        x, hit_t = fn()
        x = np.clip(x, -1, 1)
        wavfile.write(out / f"{name}.wav", SR, (x * 32767).astype(np.int16))
        index[name] = {"file": f"{name}.wav", "hit": round(float(hit_t), 4),
                       "dur": round(len(x) / SR, 4)}
        print(f"{name:16s} dur={len(x)/SR:5.2f}s hit={hit_t:5.3f}s")
    (out / "index.json").write_text(json.dumps(index, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sfx")
