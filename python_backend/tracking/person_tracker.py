"""
Person tracking = YOLOv8n (person only) + BoT-SORT (Ultralytics) + OSNet ReID.

  1. YOLO.track(..., tracker=<botsort yaml>)  -> boxes with tracker ids (motion based, short term)
  2. OSNet embeddings of each person crop     -> identity.IdentityManager
     When BoT-SORT gives a person a NEW tracker id, OSNet appearance re-links them to the
     same permanent id (P1, P2, ...) they had before.

No boxmot. Self-contained in this folder (+ export_osnet.py if you use the OSNet .pt).
"""
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from config_utils import CONFIG, resolve_model_path
from .identity import IdentityManager
from .reid_encoder import build_encoder

DEFAULTS = {
    "detector": "yolov8n.pt",
    "reid_weights": "osnet_x1_0_msmt17.pt",     # .onnx also works
    "with_reid": True,                          # False = BoT-SORT ids only (for A/B comparison)
    "imgsz": 960,
    # --- focus area: only people inside this polygon get ids / ReID (None = everyone) ---
    "roi": None,                                # [[x, y], ...] in camera pixels
    "roi_point": "centroid",                    # which point must be in the ROI: centroid | feet | either
    "roi_margin_px": 40,                        # a person already inside stays inside until this far outside
    # --- BoT-SORT (Ultralytics) ---
    "det_conf": 0.30,
    "track_high_thresh": 0.5,
    "new_track_thresh": 0.65,
    "track_buffer_s": 3.0,
    "frame_rate": 10,                           # frames per second the worker actually processes
    "gmc_method": "none",                       # fixed CCTV; "sparseOptFlow" if the camera moves
    # --- OSNet identity layer ---
    "max_ids": 0,                               # 0 = unlimited, else closed set of people
    "confirm_frames": 10,
    "confirm_min_conf": 0.5,
    "reid_assign_max": 0.22,                    # re-link only if appearance distance <= this
    "reid_new_id_min": 0.30,                    # new person only if farther than this from everyone
    "reid_gallery_accept": 0.25,
    "reid_gallery_dedup": 0.95,
    "reid_rank_margin": 0.02,
    "gallery_size": 40,
    "gallery_learn_min": 10,
    "gallery_every": 5,
    "occlusion_iou": 0.15,
    "lost_after_frames": 2,
}

YAML_PATH = Path(__file__).resolve().parent / "botsort_runtime.yaml"


def _write_botsort_yaml(cfg):
    # ReID is done by our OSNet layer, so BoT-SORT's own (YOLO-feature) ReID stays off.
    YAML_PATH.write_text(
        "tracker_type: botsort\n"
        f"track_high_thresh: {cfg['track_high_thresh']}\n"
        f"track_low_thresh: {cfg['det_conf']}\n"
        f"new_track_thresh: {cfg['new_track_thresh']}\n"
        f"track_buffer: {max(1, int(round(cfg['track_buffer_s'] * cfg['frame_rate'])))}\n"
        "match_thresh: 0.8\n"
        "fuse_score: True\n"
        f"gmc_method: {cfg['gmc_method']}\n"
        "proximity_thresh: 0.5\n"
        "appearance_thresh: 0.25\n"
        "with_reid: False\n"
        "model: auto\n"
    )
    return str(YAML_PATH)


def _parse_roi(points):
    if not points or len(points) < 3:
        return None
    return np.array(points, dtype=np.int32).reshape(-1, 1, 2)


def _find_reid(name):
    """Configured file first, then the same name as .pt / .onnx, all inside models/."""
    stem = Path(name).stem
    tried = []
    for cand in (name, stem + ".pt", stem + ".onnx"):
        if cand in tried:
            continue
        tried.append(cand)
        try:
            return resolve_model_path(cand)
        except FileNotFoundError:
            pass
    raise FileNotFoundError(f"ReID model not found in models/: tried {tried}")


class PersonTracker:
    def __init__(self, camera_id="cam", **overrides):
        cfg = dict(DEFAULTS)
        cfg.update(CONFIG.get("person_tracking", {}))
        cfg.update(overrides)
        self.cfg = cfg

        device = CONFIG.get("device", "auto")
        if device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.half = device != "cpu"

        self.detector = YOLO(resolve_model_path(cfg["detector"]))
        self.yaml_path = _write_botsort_yaml(cfg)

        self.with_reid = bool(cfg["with_reid"])
        self.encoder = None
        reid_name = "OFF"
        if self.with_reid:
            reid_path = _find_reid(cfg["reid_weights"])
            self.encoder = build_encoder(reid_path, self.device)
            reid_name = Path(reid_path).name

        self.roi = _parse_roi(cfg.get("roi"))
        self.roi_margin = float(cfg["roi_margin_px"])
        self.roi_point = cfg["roi_point"]
        if self.roi_point not in ("centroid", "feet", "either"):
            raise ValueError(f"person_tracking.roi_point must be centroid, feet or either, not {self.roi_point!r}")
        self._in_roi = set()    # tracker ids currently counted as inside the ROI (hysteresis)

        out_dir = Path(__file__).resolve().parent / "output"
        out_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.csv_path = out_dir / f"{camera_id}_{stamp}_tracks.csv"
        self.csv = open(self.csv_path, "w")
        self.csv.write("frame,time,tracker_id,person_id,state,app_dist,x1,y1,x2,y2,conf\n")
        print(f"[TRACK] per-frame log: {self.csv_path}")

        self.frame_no = 0
        self.events = []        # (frame_no, time, kind, gid, extra)
        self.ids = IdentityManager(cfg, self._event, passthrough=not self.with_reid)

        print(f"[TRACK] detector={cfg['detector']} device={self.device} "
              f"BoT-SORT(Ultralytics) ReID={reid_name} "
              f"ROI={'%d points' % len(self.roi) if self.roi is not None else 'none (everyone)'}")

    def update(self, frame):
        self.frame_no += 1
        res = self.detector.track(
            frame, persist=True, tracker=self.yaml_path, classes=[0],
            conf=self.cfg["det_conf"], imgsz=self.cfg["imgsz"],
            device=self.device, half=self.half, verbose=False,
        )[0]

        b = res.boxes
        if b is not None and b.id is not None and len(b):
            boxes = b.xyxy.cpu().numpy().astype(np.float32)
            tids = b.id.cpu().numpy().astype(int).tolist()
            confs = b.conf.cpu().numpy()
        else:
            boxes, tids, confs = np.zeros((0, 4), np.float32), [], np.zeros(0)

        # Only people inside the ROI go to the ReID / identity layer.
        inside = self._inside_mask(tids, boxes)
        idx = [i for i, v in enumerate(inside) if v]
        tids_in = [tids[i] for i in idx]
        boxes_in = boxes[idx]
        confs_in = confs[idx]

        results = self.ids.update(
            self.frame_no, tids_in, boxes_in, confs_in,
            (lambda bx: self.encoder(frame, bx)) if self.encoder else None,
        )

        out = [{"id": gid, "tid": tid, "box": tuple(float(v) for v in box),
                "conf": float(cf), "state": state, "dist": d}
               for (gid, state, d), tid, box, cf in zip(results, tids_in, boxes_in, confs_in)]
        out += [{"id": -1, "tid": tids[i], "box": tuple(float(v) for v in boxes[i]),
                 "conf": float(confs[i]), "state": "outside", "dist": None}
                for i in range(len(tids)) if not inside[i]]

        now = time.strftime("%H:%M:%S")
        for t in out:
            x1, y1, x2, y2 = t["box"]
            d = "" if t["dist"] is None else f"{t['dist']:.3f}"
            self.csv.write(f"{self.frame_no},{now},{t['tid']},{t['id']},{t['state']},{d},"
                           f"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f},{t['conf']:.2f}\n")
        if self.frame_no % 50 == 0:
            self.csv.flush()
        return out

    def _inside_mask(self, tids, boxes):
        """True for people whose CENTROID (centre of the box) is inside the ROI
        (roi_point: "feet" = bottom-centre, "either" = centroid or feet).
        Hysteresis: someone already inside stays inside until roi_margin_px outside, so a person
        standing on the edge does not flicker in and out."""
        if self.roi is None:
            return [True] * len(tids)
        mask, now = [], set()
        for t, (x1, y1, x2, y2) in zip(tids, boxes):
            cx = float((x1 + x2) / 2)
            d_centroid = cv2.pointPolygonTest(self.roi, (cx, float((y1 + y2) / 2)), True)
            d_feet = cv2.pointPolygonTest(self.roi, (cx, float(y2)), True)
            d = {"centroid": d_centroid, "feet": d_feet,
                 "either": max(d_centroid, d_feet)}[self.roi_point]
            ok = d >= (-self.roi_margin if t in self._in_roi else 0.0)
            if ok:
                now.add(t)
            mask.append(ok)
        self._in_roi = now
        return mask

    def reset(self):
        """Stream restarted: new BoT-SORT state, but keep who we already know."""
        self.detector.predictor = None
        self.ids.reset_tracks()
        print("[TRACK] tracker reset (people galleries kept)")

    def _event(self, kind, gid, extra=""):
        self.events.append((self.frame_no, time.time(), kind, gid, extra))
        who = f"P{gid}" if gid > 0 else "-"
        print(f"[TRACK] frame {self.frame_no:>6}  {kind:<8} {who:<4} {extra}")

    def summary(self):
        count = lambda k: sum(1 for e in self.events if e[2] == k)
        return {
            "frames": self.frame_no,
            "reid": "ON" if self.with_reid else "OFF",
            "ids_created": count("NEW"),
            "relinks": count("RELINK"),
            "times_lost": count("LOST"),
            "people_known": len(self.ids.people),
            "in_roi_now": len(self._in_roi) if self.roi is not None else None,
        }