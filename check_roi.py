"""Check the ROI before training: saves the full frame with the polygon drawn
and the exact 224x224 crop the model will see.

  python check_roi.py --video data/train/pack_towels/clip1.mp4 --t 1.0
"""
import argparse

import cv2

from common import ROI, make_crop, parse_roi

ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True)
ap.add_argument("--t", type=float, default=0.0, help="time in seconds")
ap.add_argument("--roi", help="ROI as JSON, e.g. '[[745,645],[819,979],[1168,885],[1041,557]]'")
a = ap.parse_args()
if a.roi:
    ROI = parse_roi(a.roi)

cap = cv2.VideoCapture(a.video)
cap.set(cv2.CAP_PROP_POS_MSEC, a.t * 1000)
ok, f = cap.read()
if not ok:
    raise SystemExit("Could not read a frame at that time.")
print(f"video size: {f.shape[1]}x{f.shape[0]}  (ROI coordinates must be in this size)")
cv2.imwrite("roi_crop_masked.png", make_crop(ROI, True)(f))
cv2.imwrite("roi_crop_plain.png", make_crop(ROI, False)(f))
cv2.polylines(f, [ROI], True, (0, 255, 0), 3)
cv2.imwrite("roi_frame.png", f)
print("Saved roi_frame.png, roi_crop_masked.png, roi_crop_plain.png")