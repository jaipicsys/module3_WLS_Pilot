"""Train pack_towels vs background for ONE operator (ROI), using frozen VideoMAE
features + logistic regression (the right choice for 6 training clips:
full fine-tuning would just memorise them).

Folder layout (full-frame clips from the camera; the ROI crop is done here):
  data/train/pack_towels/*.mp4   <- your 6 training clips (trimmed to the action)
  data/train/background/*.mp4    <- clips with NO packing (see cut_background.py)
  data/test/pack_towels/*.mp4    <- your 3 test clips
  data/test/background/*.mp4

Run:
  python train.py                 # ROI outside the polygon is masked (default)
  python train.py --no-mask       # compare: plain bounding-box crop
"""
import argparse
import os

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common import NEG, POS, ROI, Encoder, cached_features, list_videos, make_crop, parse_roi

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data")
ap.add_argument("--out", default="pack_model.joblib")
ap.add_argument("--no-mask", action="store_true")
ap.add_argument("--C", type=float, default=0.1, help="smaller = stronger regularisation")
ap.add_argument("--roi", help="ROI as JSON (default: ROI in common.py)")
a = ap.parse_args()
if a.roi:
    ROI = parse_roi(a.roi)

pos, neg = list_videos(f"{a.data}/train/{POS}"), list_videos(f"{a.data}/train/{NEG}")
print(f"train clips: {len(pos)} {POS}, {len(neg)} {NEG}")
if not pos or not neg:
    raise SystemExit(f"Need clips in BOTH {a.data}/train/{POS} and {a.data}/train/{NEG}. "
                     "With only positives the model has nothing to compare against.")

mask = not a.no_mask
tag = ("mask" if mask else "nomask") + "_" + "_".join(map(str, ROI.flatten()))
crop, enc = make_crop(ROI, mask), Encoder()

X, y, groups = [], [], []
for label, files in ((1, pos), (0, neg)):
    for p in files:
        _, x = cached_features(p, enc, crop, "cache", tag)
        X.append(x)
        y += [label] * len(x)
        groups += [os.path.basename(p)] * len(x)
        print(f"  {os.path.basename(p):40s} {len(x):4d} windows  ({'pos' if label else 'neg'})")
X, y, groups = np.concatenate(X), np.array(y), np.array(groups)
print(f"windows: {y.sum()} pos / {(1 - y).sum()} neg")


def new_model():
    return make_pipeline(StandardScaler(),
                         LogisticRegression(C=a.C, class_weight="balanced", max_iter=5000))


# Leave-one-clip-out check: each clip is predicted by a model that never saw it.
oof = np.zeros(len(y))
for tr, te in LeaveOneGroupOut().split(X, y, groups):
    if len(set(y[tr])) < 2:
        continue
    oof[te] = new_model().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
print("\nLeave-one-clip-out (window level, thr 0.5):")
print(classification_report(y, (oof >= 0.5).astype(int), target_names=[NEG, POS], digits=3))
print("Per clip (mean probability of pack_towels):")
for g in dict.fromkeys(groups):
    m = groups == g
    print(f"  {g:40s} true={'pos' if y[m][0] else 'neg'}  mean_p={oof[m].mean():.2f}")

clf = new_model().fit(X, y)
joblib.dump({"clf": clf, "mask": mask, "roi": ROI.tolist()}, a.out)
print(f"\nSaved {a.out}")