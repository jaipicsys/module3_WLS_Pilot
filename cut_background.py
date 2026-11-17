"""Cut 'background' clips (no packing) from the long video, avoiding the
pack_towels times. These are the negatives the model needs to learn what
packing is NOT (stacking, reaching, waiting...).

Example (train negatives from minutes 0-18, test negatives from 24-30):
  python cut_background.py --video packing_30min.mp4 --pack-times pack_times.csv \
      --range 0 1080 --n 20 --out data/train/background
  python cut_background.py --video packing_30min.mp4 --pack-times pack_times.csv \
      --range 1440 1800 --n 10 --out data/test/background

pack_times.csv: one row per packing instance, seconds in the long video:
  start,end
  44,49
  ...
"""
import argparse
import csv
import os
import random

import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True)
ap.add_argument("--pack-times", required=True, help="CSV with start,end (seconds)")
ap.add_argument("--range", nargs=2, type=float, required=True, help="start end (s) to sample from")
ap.add_argument("--n", type=int, default=20, help="number of clips")
ap.add_argument("--len", type=float, default=6.0, help="clip length (s)")
ap.add_argument("--margin", type=float, default=2.0, help="keep this far from any packing (s)")
ap.add_argument("--out", required=True)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

with open(a.pack_times) as f:
    pack = [(float(r["start"]), float(r["end"])) for r in csv.DictReader(f)]
busy = [(s - a.margin, e + a.margin) for s, e in pack]


def free(s, e, taken):
    return all(e <= bs or s >= be for bs, be in busy + taken)


rng = random.Random(a.seed)
lo, hi = a.range
taken, tries = [], 0
while len(taken) < a.n and tries < 20000:
    tries += 1
    s = rng.uniform(lo, hi - a.len)
    if free(s, s + a.len, taken):
        taken.append((s, s + a.len))
if len(taken) < a.n:
    print(f"Only found {len(taken)} free slots in that range.")
taken.sort()

cap = cv2.VideoCapture(a.video)
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
os.makedirs(a.out, exist_ok=True)
stem = os.path.splitext(os.path.basename(a.video))[0]
for s, e in taken:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(s * fps)))
    name = os.path.join(a.out, f"bg_{stem}_{int(s):05d}s.mp4")
    wr = cv2.VideoWriter(name, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    for _ in range(int(round((e - s) * fps))):
        ok, f = cap.read()
        if not ok:
            break
        wr.write(f)
    wr.release()
    print(f"{name}  ({s:.1f}-{e:.1f}s)")