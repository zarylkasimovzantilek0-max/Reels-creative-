"""Mix voice + music bed + SFX for a reel, following an edit plan.

voice : high-pass, light denoise, presence EQ, compression (ffmpeg), ~-16 LUFS
music : ducked under the voice (bed_gain_db_speech) and lifted in pauses (bed_gain_db_gap)
sfx   : placed so each sound's "hit" point lands on its plan time
master: two-pass loudnorm to -14 LUFS / -1 dBTP (Instagram / TikTok loudness)

Usage:  python3 tools/mix_audio.py SRC.mp4 plan.json music.wav sfx_dir OUT.wav
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000


def read_wav(p):
    sr, x = wavfile.read(p)
    assert sr == SR, (p, sr)
    x = x.astype(np.float32) / (32768 if x.dtype == np.int16 else 1)
    return x if x.ndim == 2 else np.stack([x, x], 1)


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def loudnorm_json(path, target="I=-16:TP=-1.5:LRA=11"):
    chain = f"loudnorm={target}:print_format=json"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", chain, "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1]
    return json.loads(txt)


def process_voice(src, tmp):
    raw = f"{tmp}/voice_raw.wav"
    out = f"{tmp}/voice.wav"
    chain = ("highpass=f=85,afftdn=nf=-35:nr=8,"
             "equalizer=f=220:t=q:w=1.2:g=-2,equalizer=f=3200:t=q:w=1.0:g=3,"
             "equalizer=f=9000:t=h:w=0.7:g=2,"
             "acompressor=threshold=-26dB:ratio=3:attack=6:release=90:makeup=4")
    ffmpeg("-i", src, "-vn", "-ac", "2", "-ar", str(SR), "-af", chain, raw)
    m = loudnorm_json(raw)
    ffmpeg("-i", raw, "-af",
           f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
           f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
           "-ar", str(SR), out)
    return read_wav(out)


def lufs(path):
    return float(loudnorm_json(path)["input_i"])


def voice_activity(v, speech):
    """Smooth 0..1 envelope: 1 while talking. Uses the plan's speech segments + a level gate."""
    n = len(v)
    act = np.zeros(n, np.float32)
    for a, b in speech:
        act[int(a * SR):int(b * SR)] = 1.0
    # one-pole attack/release smoothing
    att, rel = np.exp(-1 / (0.06 * SR)), np.exp(-1 / (0.35 * SR))
    out = np.empty_like(act)
    y = 0.0
    for i in range(0, n, 48):              # 1 ms steps are plenty
        x = act[i]
        c = att if x > y else rel
        y = c * y + (1 - c) * x
        out[i:i + 48] = y
    return out


def main(src, plan_path, music_path, sfx_dir, out_path):
    plan = json.load(open(plan_path))
    sfx_dir = Path(sfx_dir)
    index = json.loads((sfx_dir / "index.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        voice = process_voice(src, tmp)
        n = len(voice)
        music = read_wav(music_path)[:n]
        music = np.pad(music, ((0, n - len(music)), (0, 0)))
        m_lufs = lufs(music_path)

    # ---- music bed with ducking (levels relative to the -16 LUFS voice)
    mp = plan["music"]
    g_speech = 10 ** ((-16 + mp["bed_gain_db_speech"] - m_lufs) / 20)
    g_gap = 10 ** ((-16 + mp["bed_gain_db_gap"] - m_lufs) / 20)
    act = voice_activity(voice, plan["speech"])
    # carve a little 1-4 kHz room for the voice in the music while talking
    sos = butter(2, [1000, 4000], "band", fs=SR, output="sos")
    mid = sosfilt(sos, music, axis=0)
    music_carved = music - mid * (0.45 * act[:, None])
    bed = music_carved * (g_gap + (g_speech - g_gap) * act)[:, None]

    # ---- sfx
    sfx = np.zeros((n, 2), np.float32)
    bus = 0.5                                       # -6 dB SFX bus
    for t, name, gain in plan["sfx"]:
        meta = index[name]
        x = read_wav(sfx_dir / meta["file"])
        start = int(round((t - meta["hit"]) * SR))
        if start < 0:
            x = x[-start:]
            start = 0
        end = min(n, start + len(x))
        sfx[start:end] += x[: end - start] * gain * bus

    mix = voice + bed + sfx
    with tempfile.TemporaryDirectory() as tmp:
        pre = f"{tmp}/premaster.wav"
        wavfile.write(pre, SR, np.clip(mix, -1, 1).astype(np.float32))
        stems = Path(out_path).with_suffix("")
        for name, x in (("voice", voice), ("music", bed), ("sfx", sfx)):
            wavfile.write(f"{stems}_{name}.wav", SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
        m = loudnorm_json(pre, "I=-14:TP=-1:LRA=11")
        ffmpeg("-i", pre, "-af",
               f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
               f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
               "alimiter=limit=0.89:attack=3:release=50:level=false",
               "-ar", str(SR), "-c:a", "pcm_s16le", out_path)
    print("mix written", out_path)


if __name__ == "__main__":
    main(*sys.argv[1:6])
