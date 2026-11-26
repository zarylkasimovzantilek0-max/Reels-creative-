"""Royalty-free background beat for reels, synthesized from scratch.

Upbeat pop / lo-fi trap bed (default 95 BPM, C-G-Am-F) with kick, clap, hats,
808 sub, side-chained pad and a plucked arp.  Arrangement hooks driven by the
edit plan: a drum break around a transition, drums ending before the outro and
a fade-out.

Usage:  python3 tools/music_synth.py projects/dentist-reel/edit_plan.json out.wav [duration]
"""
import json
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
rng = np.random.default_rng(11)


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def place(buf, x, at):
    i = int(round(at * SR))
    if i >= len(buf) or i + len(x) <= 0:
        return
    j = min(len(buf), i + len(x))
    buf[i:j] += x[: j - i]


# ------------------------------------------------------------- instruments
def kick():
    t = np.arange(int(0.45 * SR)) / SR
    f = 48 + 110 * np.exp(-t / 0.035)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)
    x += hp(rng.standard_normal(len(t)), 3000) * np.exp(-t / 0.003) * 0.25
    return np.tanh(1.6 * x)


def clap():
    t = np.arange(int(0.35 * SR)) / SR
    n = sosfilt(butter(2, [900, 5000], "band", fs=SR, output="sos"), rng.standard_normal(len(t)))
    env = np.zeros_like(t)
    for d in (0.0, 0.011, 0.022):
        m = t >= d
        env[m] += np.exp(-(t[m] - d) / 0.008)
    env += np.exp(-t / 0.12) * 0.5
    return n * env * 0.6


def hat(open_=False):
    dur = 0.3 if open_ else 0.06
    t = np.arange(int(dur * SR)) / SR
    x = hp(rng.standard_normal(len(t)), 7000) * np.exp(-t / (0.09 if open_ else 0.012))
    return x * (0.22 if open_ else 0.18)


def sub808(freq, dur):
    t = np.arange(int(dur * SR)) / SR
    f = freq * (1 + 0.6 * np.exp(-t / 0.02))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    env = np.minimum(1, t / 0.005) * np.exp(-t / (dur * 0.9))
    rel = int(0.03 * SR)
    env[-rel:] *= np.linspace(1, 0, rel)
    y = x * env
    # upper harmonics so the bass line is audible on phone speakers
    return (np.tanh(1.4 * y) + 0.25 * np.tanh(4 * y)) * 0.7


def saw(freq, t, detune=0.0):
    ph = (freq * (1 + detune) * t + rng.uniform()) % 1.0
    return 2 * ph - 1


def pad_chord(notes, dur):
    t = np.arange(int(dur * SR)) / SR
    x = np.zeros_like(t)
    for m in notes:
        f = midi_hz(m)
        for d in (-0.006, 0.0, 0.007):
            x += saw(f, t, d)
    x = lp(x / (len(notes) * 3), 2200)
    env = np.minimum(1, t / 0.25) * np.minimum(1, (dur - t) / 0.2)
    return x * env * 0.5


def pluck(freq, dur=0.35):
    t = np.arange(int(dur * SR)) / SR
    x = np.sign(np.sin(2 * np.pi * freq * t)) * 0.5 + np.sin(2 * np.pi * freq * 2 * t) * 0.3
    x = lp(x, 3200) * np.exp(-t / 0.11)
    return x * 0.25


def reverse_cymbal(dur=0.6):
    t = np.arange(int(dur * SR)) / SR
    x = hp(rng.standard_normal(len(t)), 5000) * (t / dur) ** 3
    return x * 0.35


def crash():
    t = np.arange(int(1.6 * SR)) / SR
    return hp(rng.standard_normal(len(t)), 4500) * np.exp(-t / 0.5) * 0.28


# ------------------------------------------------------------- arrangement
CHORDS = [  # (bass midi, pad voicing, arp notes)
    (36, [60, 64, 67, 71], [72, 76, 79, 83]),   # Cmaj7
    (43, [59, 62, 67, 69], [71, 74, 79, 81]),   # G6/add9 feel
    (45, [60, 64, 69, 71], [72, 76, 81, 83]),   # Am(add9)
    (41, [60, 65, 69, 72], [72, 77, 81, 84]),   # Fmaj
]


def build(plan, total):
    m = plan["music"]
    bpm = m["bpm"]
    beat = 60.0 / bpm
    step = beat / 4
    bar = beat * 4
    brk0, brk1 = m["drum_break"]
    end_drums = m["end_drums"]
    n = int((total + 3) * SR)
    drums, bass, pad, arp = (np.zeros(n) for _ in range(4))
    kicks = []

    K, C, H, OH = kick(), clap(), hat(), hat(True)
    kick_steps = {0, 6, 10}
    clap_steps = {4, 12}
    bars = int(np.ceil(total / bar)) + 1
    for b in range(bars):
        root, voicing, arp_notes = CHORDS[b % 4]
        t0 = b * bar
        # pad + bass are continuous (they carry the break and the outro)
        place(pad, pad_chord(voicing, bar + 0.25), t0)
        for s in range(16):
            t = t0 + s * step
            if t > total + 1:
                break
            in_break = brk0 <= t < brk1
            drums_on = t < end_drums and not in_break
            if s in kick_steps:
                place(bass, sub808(midi_hz(root), step * (6 if s == 0 else 4) * 0.95), t)
            if drums_on:
                if s in kick_steps:
                    place(drums, K, t)
                    kicks.append(t)
                if s in clap_steps:
                    place(drums, C, t)
                if s % 2 == 0:
                    place(drums, H * (1.0 if s % 4 == 0 else 0.7), t)
                if b % 2 == 1 and s >= 12:          # 16th hat roll at the end of every 2nd bar
                    place(drums, H * 0.55, t + step / 2)
                if s == 14 and b % 2 == 0:
                    place(drums, OH, t)
            if s % 2 == 0 and t < total:           # 8th-note arp
                note = arp_notes[(s // 2) % 4] if (s // 2) % 8 < 4 else arp_notes[3 - (s // 2) % 4]
                place(arp, pluck(midi_hz(note)) * (0.9 if s % 4 == 0 else 0.6), t)
    # transition ear-candy: reverse cymbal into the end of the break + crash on re-entry
    rc = reverse_cymbal(brk1 - brk0 + 0.05)
    place(drums, rc, brk1 - len(rc) / SR)
    place(drums, crash(), brk1)
    kicks.append(brk1)
    place(drums, K, brk1)
    place(drums, crash() * 0.8, 0.0)

    # side-chain pump on pad + arp from the kicks
    pump = np.ones(n)
    for k in kicks:
        i = int(k * SR)
        L = int(0.28 * SR)
        j = min(n, i + L)
        pump[i:j] = np.minimum(pump[i:j], 0.35 + 0.65 * (np.linspace(0, 1, j - i) ** 0.7))
    pad *= pump
    arp_d = arp.copy()
    d = int(beat * 0.75 * SR)
    arp_d[d:] += arp[:-d] * 0.35                 # dotted-8th delay
    arp_d *= pump

    mix_mono_low = drums * 0.85 + bass * 0.4
    # stereo: pad wide (Haas), arp ping-pong, drums/bass centre
    hz = int(0.012 * SR)
    padL = pad
    padR = np.concatenate([np.zeros(hz), pad[:-hz]])
    arpL = arp_d * 0.8 + np.concatenate([np.zeros(d), arp[:-d]]) * 0.1
    arpR = arp_d * 0.6 + np.concatenate([np.zeros(2 * d), arp[:-2 * d]]) * 0.25
    L = mix_mono_low + padL * 1.7 + arpL * 1.4
    R = mix_mono_low + padR * 1.7 + arpR * 1.4
    st = np.stack([L, R], 1)

    # light room reverb on everything except low end
    ir_t = np.arange(int(0.8 * SR)) / SR
    ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.18)
    ir = lp(ir, 6000)
    ir /= np.sqrt(np.sum(ir ** 2))
    for c in range(2):
        wet = fftconvolve(hp(st[:, c], 300), ir)[:n]
        st[:, c] = st[:, c] + wet * 0.12

    st = st[: int(total * SR)]
    f0, f1 = m["fade_out"]
    tt = np.arange(len(st)) / SR
    fade = np.clip((f1 - tt) / (f1 - f0), 0, 1) ** 1.5
    st *= fade[:, None]
    st /= np.max(np.abs(st)) + 1e-9
    return st * 0.9


def main(plan_path, out_path, total=None):
    plan = json.load(open(plan_path))
    total = float(total) if total else plan["zoom"][-1][0]
    st = build(plan, total)
    wavfile.write(out_path, SR, (st * 32767).astype(np.int16))
    print("music", out_path, f"{len(st)/SR:.2f}s")


if __name__ == "__main__":
    main(*sys.argv[1:])
