"""Shared helpers: ROI crop, sliding 2-s windows, VideoMAE feature extractor."""
import os
from collections import deque

import cv2
import numpy as np
import torch

# ---- Settings ---------------------------------------------------------------
# ROI polygon for the pack_towels operator, in ORIGINAL video pixel coordinates.
ROI = np.array([[608, 429], [687, 664], [917, 576], [753, 354]], np.int32)

T = 16            # frames per window (what VideoMAE expects)
SIZE = 224        # VideoMAE input size
WIN_SEC = 2.0     # each window covers ~2 s of video
HOP_SEC = 0.5     # a new window every 0.5 s
MODEL_ID = os.environ.get("VIDEOMAE_ID", "MCG-NJU/videomae-base-finetuned-kinetics")

POS, NEG = "pack_towels", "background"
VIDEO_EXT = (".mp4", ".avi", ".mov", ".mkv")

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def parse_roi(text):
    """'[[745,645],[819,979],[1168,885],[1041,557]]' -> int32 array (N,2)."""
    import json
    roi = np.array(json.loads(text), np.int32)
    if roi.ndim != 2 or roi.shape[1] != 2 or len(roi) < 3:
        raise ValueError("ROI must be a list of [x, y] points, at least 3")
    return roi


# ---- ROI crop ---------------------------------------------------------------
def make_crop(roi=ROI, mask=True):
    """Return f(frame)->224x224 BGR crop of the ROI's bounding square.
    With mask=True, pixels outside the polygon are blacked out so neighbours
    don't leak into the clip."""
    x, y, w, h = cv2.boundingRect(roi)
    s = max(w, h)
    x0, y0 = int(x + w / 2 - s / 2), int(y + h / 2 - s / 2)
    m = np.zeros((s, s), np.uint8)
    cv2.fillPoly(m, [roi - [x0, y0]], 1)

    def crop(frame):
        H, W = frame.shape[:2]
        out = np.zeros((s, s, 3), np.uint8)
        xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + s, W), min(y0 + s, H)
        if xb > xa and yb > ya:
            out[ya - y0:yb - y0, xa - x0:xb - x0] = frame[ya:yb, xa:xb]
        if mask:
            out *= m[..., None]
        return cv2.resize(out, (SIZE, SIZE))

    return crop


# ---- Sliding windows --------------------------------------------------------
def iter_windows(path, crop, hop_sec=HOP_SEC):
    """Yield (centre_time_s, window[T,224,224,3] BGR uint8) over a video.
    Clips shorter than WIN_SEC give one window sampled across the whole clip."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"Cannot open {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    span = max(T, int(round(WIN_SEC * fps)))
    idx = np.linspace(0, span - 1, T).round().astype(int)
    hop = max(1, int(round(hop_sec * fps)))
    buf, n, emitted = deque(maxlen=span), 0, False
    while True:
        ok, f = cap.read()
        if not ok:
            break
        buf.append(crop(f))
        n += 1
        if len(buf) == span and (n - span) % hop == 0:
            yield (n - span / 2) / fps, np.stack([buf[i] for i in idx])
            emitted = True
    cap.release()
    if not emitted and len(buf) > 0:
        frames = list(buf)
        j = np.linspace(0, len(frames) - 1, T).round().astype(int)
        yield len(frames) / 2 / fps, np.stack([frames[i] for i in j])


# ---- VideoMAE encoder (frozen) ----------------------------------------------
class Encoder:
    def __init__(self, model_id=MODEL_ID, device=None):
        from transformers import VideoMAEModel
        self.dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = VideoMAEModel.from_pretrained(model_id).to(self.dev).eval()

    @torch.no_grad()
    def __call__(self, windows):
        x = np.stack(windows)[..., ::-1].astype(np.float32) / 255.0   # BGR->RGB
        x = (x - MEAN) / STD
        x = torch.from_numpy(x).permute(0, 1, 4, 2, 3).to(self.dev)    # B,T,C,H,W
        with torch.autocast("cuda", dtype=torch.float16, enabled=self.dev == "cuda"):
            h = self.model(pixel_values=x).last_hidden_state.mean(1)
        return h.float().cpu().numpy()


def video_features(path, enc, crop, batch=8):
    """Return (times[N], features[N, D]) for every window in a video."""
    times, feats, buf = [], [], []
    cap = cv2.VideoCapture(path)
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 25.0)
    cap.release()
    show = dur > 60                                  # progress only for long videos
    for t, w in iter_windows(path, crop):
        if show and len(times) % 40 == 0:
            print(f"\r  features: {t / 60:5.1f} / {dur / 60:.1f} min", end="", flush=True)
        times.append(t)
        buf.append(w)
        if len(buf) == batch:
            feats.append(enc(buf))
            buf = []
    if buf:
        feats.append(enc(buf))
    if show:
        print()
    if not feats:
        return np.zeros(0), np.zeros((0, 0), np.float32)
    return np.array(times), np.concatenate(feats)


def cached_features(path, enc, crop, cache_dir, tag):
    """Feature extraction with an on-disk cache (re-runs are instant)."""
    os.makedirs(cache_dir, exist_ok=True)
    key = os.path.join(cache_dir, f"{tag}__{os.path.basename(path)}.npz")
    if os.path.exists(key) and os.path.getmtime(key) > os.path.getmtime(path):
        d = np.load(key)
        return d["t"], d["x"]
    t, x = video_features(path, enc, crop)
    np.savez(key, t=t, x=x)
    return t, x


def list_videos(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(VIDEO_EXT))


def draw_overlay(frame, prob, thr, roi=ROI):
    """Draw ROI polygon (green = pack_towels, red = not) and the probability."""
    on = prob is not None and prob >= thr
    col = (0, 200, 0) if on else (0, 0, 255)
    cv2.polylines(frame, [roi], True, col, 3)
    txt = "--" if prob is None else f"pack_towels {prob:.2f}"
    x, y = roi[:, 0].min(), roi[:, 1].min() - 10
    cv2.putText(frame, txt, (int(x), int(max(y, 20))), cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, 2)
    return frame