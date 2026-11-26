"""Render the zoom-in / zoom-out edit of a talking-head video from an edit plan.

* face-tracked zoom (Haar cascade, heavily smoothed) so close-ups stay on the face
* easing per keyframe: hold | linear | ease | expo | punch
* zoom < 1 turns the shot into a rounded "card" over a light background (reference look)
* motion blur on fast zoom moves (sub-frame accumulation)
* fx: shake, flash (light-leak sweep), blur (defocus transition)
* light grade + sharpening for the upscale to 1080x1920

Usage:  python3 tools/render_video.py SRC.mp4 projects/x/edit_plan.json OUT_video_only.mp4
"""
import json
import math
import subprocess
import sys

import cv2
import numpy as np


# ------------------------------------------------------------- easing / keyframes
def ease_fn(kind, u):
    u = min(max(u, 0.0), 1.0)
    if kind == "hold":
        return 0.0 if u < 1.0 else 1.0
    if kind == "linear":
        return u
    if kind == "ease":                     # cubic in-out
        return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
    if kind == "expo":                     # fast start, long settle
        return 1.0 if u >= 1 else 1 - 2 ** (-10 * u)
    if kind == "punch":                    # snappy with a little overshoot
        c1, c3 = 1.70158, 2.70158
        return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2
    raise ValueError(kind)


def make_zoom(keys):
    keys = [(float(t), float(z), e) for t, z, e in keys]

    def zoom(t):
        if t <= keys[0][0]:
            return keys[0][1]
        for (t0, z0, _), (t1, z1, e) in zip(keys, keys[1:]):
            if t0 <= t <= t1:
                if t1 == t0:
                    return z1
                return z0 + (z1 - z0) * ease_fn(e, (t - t0) / (t1 - t0))
        return keys[-1][1]
    return zoom


# ------------------------------------------------------------- face track
def face_track(path, fps):
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(path)
    pts, i = [], 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % 6 == 0:
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            fs = casc.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
            if len(fs):
                x, y, w, h = max(fs, key=lambda r: r[2] * r[3])
                pts.append((i / fps, (x + w / 2) / fr.shape[1], (y + h / 2) / fr.shape[0]))
        i += 1
    cap.release()
    a = np.array(pts)
    # heavy smoothing (~1.2 s) so the camera feels locked-off, not "tracking"
    k = 13
    pad = lambda v: np.concatenate([np.full(k, v[0]), v, np.full(k, v[-1])])
    ker = np.hanning(2 * k + 1); ker /= ker.sum()
    sx = np.convolve(pad(a[:, 1]), ker, "same")[k:-k]
    sy = np.convolve(pad(a[:, 2]), ker, "same")[k:-k]
    return lambda t: (float(np.interp(t, a[:, 0], sx)), float(np.interp(t, a[:, 0], sy)))


# ------------------------------------------------------------- fx envelopes
def fx_value(fx, kind, t):
    v = 0.0
    for f in fx:
        if f["type"] != kind or not (f["t"] <= t <= f["t"] + f["dur"]):
            continue
        u = (t - f["t"]) / f["dur"]
        if kind == "shake":
            v = max(v, f["amount"] * (1 - u) ** 2)
        elif kind == "blur":
            shape = f.get("shape", "tri")
            e = (1 - u) ** 2 if shape == "out" else max(0.0, math.sin(math.pi * u)) ** 1.5
            v = max(v, f["amount"] * e)
        elif kind == "flash":
            v = max(v, u)                   # progress through the sweep
    return v


def flash_amount(fx, t):
    for f in fx:
        if f["type"] == "flash" and f["t"] <= t <= f["t"] + f["dur"]:
            return f, min(1.0, (t - f["t"]) / f["dur"])
    return None, 0.0


# ------------------------------------------------------------- frame ops
W, H = 1080, 1920


def grade(fr):
    x = fr.astype(np.float32) / 255
    x = np.clip((x - 0.5) * 1.06 + 0.5 + 0.01, 0, 1)            # contrast
    hsv = cv2.cvtColor(x, cv2.COLOR_BGR2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.12, 0, 1)                # saturation
    x = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return x


def make_background():
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(-1, 1, W)[None, :]
    top = np.array([0.965, 0.955, 0.950])[None, None, :]            # BGR, soft light grey
    bot = np.array([0.860, 0.845, 0.835])[None, None, :]
    bg = top + (bot - top) * y[..., None]
    vign = 1 - 0.10 * (x ** 2)[..., None] - 0.06 * ((y - 0.45) ** 2)[..., None]
    return (bg * vign).astype(np.float32)


BG = make_background()


def rounded_mask(w, h, r):
    m = np.zeros((h, w), np.float32)
    r = int(max(0, min(r, w // 2, h // 2)))
    if r == 0:
        m[:] = 1
        return m
    cv2.rectangle(m, (r, 0), (w - r - 1, h - 1), 1, -1)
    cv2.rectangle(m, (0, r), (w - 1, h - r - 1), 1, -1)
    for cx, cy in ((r, r), (w - r - 1, r), (r, h - r - 1), (w - r - 1, h - r - 1)):
        cv2.circle(m, (cx, cy), r, 1, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(m, (3, 3), 0)


def render_subframe(src, z, face, shake_xy):
    sh, sw = src.shape[:2]
    s0 = max(W / sw, H / sh)
    dx, dy = shake_xy
    if z >= 1.0:
        s = s0 * z
        ws, hs = W / s, H / s
        fx, fy = face
        cx = fx * sw
        cy = fy * sh + (0.5 - 0.40) * hs           # face sits at 40 % of screen height
        cx = min(max(cx, ws / 2), sw - ws / 2)
        cy = min(max(cy, hs / 2), sh - hs / 2)
        M = np.float32([[s, 0, W / 2 - s * cx + dx], [0, s, H / 2 - s * cy + dy]])
        return cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LANCZOS4,
                              borderMode=cv2.BORDER_REFLECT)
    # ---- card mode
    s = s0 * z
    cw, ch = int(round(sw * s)), int(round(sh * s))
    card = cv2.resize(src, (cw, ch), interpolation=cv2.INTER_LANCZOS4 if z > 0.5 else cv2.INTER_AREA)
    k = min(1.0, (1 - z) / 0.16)
    radius = 46 * k
    mask = rounded_mask(cw, ch, radius)
    ox = int(round(W / 2 - cw / 2 + dx))
    oy = int(round(H / 2 - ch / 2 - 30 * k + dy))
    out = BG.copy()
    # drop shadow
    sm = np.zeros((H, W), np.float32)
    paste_max(sm, mask, ox, oy + 22)
    sm = cv2.GaussianBlur(sm, (0, 0), 28) * 0.38 * k
    out *= (1 - sm)[..., None]
    y0, x0 = max(0, oy), max(0, ox)
    y1, x1 = min(H, oy + ch), min(W, ox + cw)
    cm = mask[y0 - oy:y1 - oy, x0 - ox:x1 - ox][..., None]
    out[y0:y1, x0:x1] = card[y0 - oy:y1 - oy, x0 - ox:x1 - ox] * cm + out[y0:y1, x0:x1] * (1 - cm)
    return out


def paste_max(canvas, patch, x, y):
    """Paste a 2-D patch onto canvas at (x, y), clipped to the canvas bounds."""
    ph, pw = patch.shape
    y0, x0 = max(0, y), max(0, x)
    y1, x1 = min(canvas.shape[0], y + ph), min(canvas.shape[1], x + pw)
    if y1 > y0 and x1 > x0:
        canvas[y0:y1, x0:x1] = np.maximum(canvas[y0:y1, x0:x1], patch[y0 - y:y1 - y, x0 - x:x1 - x])


def apply_flash(img, f, u):
    # diagonal light-leak band sweeping left -> right, screen-blended, plus a brief exposure lift
    yy, xx = np.mgrid[0:H:4, 0:W:4].astype(np.float32)
    pos = -500 + u * (W + 1000)
    d = (xx - pos) + (yy - H / 2) * 0.35
    band = np.exp(-(d / 210) ** 2)
    band = cv2.resize(band, (W, H), interpolation=cv2.INTER_LINEAR)
    env = max(0.0, math.sin(math.pi * u)) ** 0.8 * f["amount"]
    tint = np.array([1.0, 0.97, 0.92], np.float32)                 # BGR: warm white
    a = (band * env)[..., None] * tint
    img = 1 - (1 - img) * (1 - a)
    lift = 0.22 * env
    return np.clip(img + lift * (1 - img), 0, 1)


def sharpen(img, amount=0.35, sigma=1.1):
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return np.clip(img + amount * (img - blur), 0, 1)


# ------------------------------------------------------------- main
def main(src_path, plan_path, out_path):
    plan = json.load(open(plan_path))
    fps = plan["output"]["fps"]
    zoom = make_zoom(plan["zoom"])
    fx = plan["fx"]

    cap = cv2.VideoCapture(src_path)
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    n_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = n_src / src_fps
    face = face_track(src_path, src_fps)

    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", out_path], stdin=subprocess.PIPE)

    n_out = int(math.floor(duration * fps))
    cur_idx, cur = -1, None
    rng = np.random.default_rng(3)
    shake_phase = rng.uniform(0, 100, 4)
    for n in range(n_out):
        t = n / fps
        want = min(n_src - 1, int(round(t * src_fps)))
        while cur_idx < want:
            ok, fr = cap.read()
            if not ok:
                break
            cur_idx += 1
            if cur_idx == want:
                cur = grade(fr)
        # motion blur for fast zoom moves (180-degree shutter)
        shutter = 0.5 / fps
        z0, z1 = zoom(t - shutter / 2), zoom(t + shutter / 2)
        edge_px = abs(z1 - z0) / max(min(z0, z1), 0.5) * H / 2
        k = 1 if edge_px < 3 else min(9, int(edge_px / 2.5) + 2)
        acc = None
        for j in range(k):
            ts = t + ((j + 0.5) / k - 0.5) * shutter if k > 1 else t
            amp = fx_value(fx, "shake", ts)
            sx = amp * (math.sin(ts * 71 + shake_phase[0]) * 0.6 + math.sin(ts * 113 + shake_phase[1]) * 0.4)
            sy = amp * (math.sin(ts * 83 + shake_phase[2]) * 0.6 + math.sin(ts * 127 + shake_phase[3]) * 0.4)
            sub = render_subframe(cur, zoom(ts), face(t), (sx, sy))
            acc = sub if acc is None else acc + sub
        img = acc / k
        b = fx_value(fx, "blur", t)
        if b > 0.3:
            img = cv2.GaussianBlur(img, (0, 0), b)
        f, u = flash_amount(fx, t)
        if f is not None:
            img = apply_flash(img, f, u)
        img = sharpen(img)
        enc.stdin.write((img * 255 + 0.5).astype(np.uint8).tobytes())
        if n % 60 == 0:
            print(f"frame {n}/{n_out}  t={t:5.2f}  zoom={zoom(t):.3f}  mb={k}", flush=True)
    enc.stdin.close()
    enc.wait()
    print("video written", out_path)


if __name__ == "__main__":
    main(*sys.argv[1:4])
