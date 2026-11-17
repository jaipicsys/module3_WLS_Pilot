"""Test the pack_towels model.

1) Labelled test clips (data/test/pack_towels, data/test/background):
     python test.py                       # scores per window and per clip
     python test.py --vis-dir vis         # also save each clip with overlay

2) Any video, e.g. the test minutes of the long video (no labels needed):
     python test.py --video packing_30min.mp4 --vis vis_full.mp4
   Prints the time ranges where packing was detected.
"""
import argparse
import os

import cv2
import joblib
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

from common import (NEG, POS, Encoder, draw_overlay, list_videos, make_crop,
                    parse_roi, video_features)

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="pack_model.joblib")
ap.add_argument("--data", default="data")
ap.add_argument("--thr", type=float, default=0.5)
ap.add_argument("--vis-dir", help="save labelled test clips with overlay here")
ap.add_argument("--video", help="run on one (unlabelled) video instead")
ap.add_argument("--vis", help="output video path for --video mode")
ap.add_argument("--roi", help="test on a different operator's ROI, e.g. "
                "'[[745,645],[819,979],[1168,885],[1041,557]]' (default: the training ROI)")
a = ap.parse_args()

M = joblib.load(a.model)
clf = M["clf"]
roi = parse_roi(a.roi) if a.roi else np.array(M["roi"], np.int32)
print(f"ROI: {roi.tolist()}")
crop, enc = make_crop(roi, M["mask"]), Encoder()


def predict(path):
    t, x = video_features(path, enc, crop)
    return t, (clf.predict_proba(x)[:, 1] if len(x) else np.zeros(0))


def write_vis(src, dst, times, probs):
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    wr = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    n = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        p = None
        if len(times):
            k = np.abs(times - n / fps).argmin()
            p = probs[k] if abs(times[k] - n / fps) <= 1.0 else None
        wr.write(draw_overlay(f, p, a.thr, roi))
        n += 1
        if n % (int(fps) * 30) == 0:
            print(f"\r  writing video: {n / fps / 60:5.1f} min", end="", flush=True)
    print()
    wr.release()


def segments(times, probs, thr, hop=0.5):
    out, start = [], None
    for t, p in zip(times, probs):
        if p >= thr and start is None:
            start = t
        if p < thr and start is not None:
            out.append((start, t - hop))
            start = None
    if start is not None:
        out.append((start, times[-1]))
    return out


if a.video:   # ---------------- unlabelled video mode ----------------
    t, p = predict(a.video)
    print(f"{len(t)} windows. Packing detected (window centres, s):")
    for s, e in segments(t, p, a.thr):
        print(f"  {s:8.1f} - {e:8.1f}   ({int(s // 60):02d}:{s % 60:04.1f} - {int(e // 60):02d}:{e % 60:04.1f})")
    if a.vis:
        write_vis(a.video, a.vis, t, p)
        print(f"Saved {a.vis}")
    raise SystemExit

# ---------------- labelled test clips ----------------
Y, P, rows = [], [], []
for label, name in ((1, POS), (0, NEG)):
    for path in list_videos(f"{a.data}/test/{name}"):
        t, p = predict(path)
        Y += [label] * len(p)
        P += list(p)
        frac = float((p >= a.thr).mean()) if len(p) else 0.0
        rows.append((os.path.basename(path), label, len(p), p.mean() if len(p) else 0, frac))
        if a.vis_dir:
            os.makedirs(a.vis_dir, exist_ok=True)
            write_vis(path, os.path.join(a.vis_dir, os.path.basename(path)), t, p)

if not rows:
    raise SystemExit(f"No test clips in {a.data}/test/{POS} or {a.data}/test/{NEG}")

Y, P = np.array(Y), np.array(P)
pred = (P >= a.thr).astype(int)
print(f"\nWINDOW level (thr {a.thr}):")
print(classification_report(Y, pred, labels=[0, 1], target_names=[NEG, POS], digits=3, zero_division=0))
print("confusion [rows=true neg,pos | cols=pred neg,pos]:\n", confusion_matrix(Y, pred, labels=[0, 1]))

print("\nCLIP level (clip = pack_towels if mean probability >= thr):")
print(f"  {'clip':40s} {'true':6s} {'windows':>7s} {'mean_p':>7s} {'%win>thr':>9s}  pred   ok")
correct = 0
for name, label, n, mp, frac in rows:
    pr = int(mp >= a.thr)
    correct += pr == label
    print(f"  {name:40s} {'pos' if label else 'neg':6s} {n:7d} {mp:7.2f} {frac:9.0%}  "
          f"{'pos' if pr else 'neg':5s}  {'✓' if pr == label else '✗'}")
print(f"\nClip accuracy: {correct}/{len(rows)}")
if a.vis_dir:
    print(f"Overlay videos saved in {a.vis_dir}/")