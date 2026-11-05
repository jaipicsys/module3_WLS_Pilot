"""
Person tracking for the operator logic (one instance per camera).

Uses track_people_osnet_frozen.py as-is:
  short term : YOLO person model + BoT-SORT (model.track, persist=True)
  long term  : GlobalIDManager -> stable P-IDs (P1..Pmax_ids), OSNet appearance,
               frozen gallery learnt in each person's first learn_s seconds

track_people_osnet_frozen.py and export_osnet.py must sit next to this file
(OSNet's architecture is imported from export_osnet.py).

update(frame) returns one dict per tracked person:
  {"gid": 3 or -1, "lid": tracker id, "state": "tracked"/"pending"/"unknown"/...,
   "box": np.array([x1, y1, x2, y2]), "conf": float, "app_dist": float}
gid -1 = the tracker sees a person but no P-ID is trusted yet (grey "?").
"""

import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

import track_people_osnet_frozen as tp
from config_utils import BASE_DIR, CONFIG, resolve_model_path

_ARGS_LOCK = threading.Lock()


def _default_args():
    """All tracker defaults from track_people_osnet_frozen.parse_args(),
    without letting it read app.py's command line."""
    with _ARGS_LOCK:
        saved = sys.argv
        sys.argv = [saved[0] if saved else "tracker"]
        try:
            return tp.parse_args()
        finally:
            sys.argv = saved


class PersonTracker:
    def __init__(self, camera_id, device, half, fallback_weights=None, fallback_class=0,
                 roi=None):
        cfg = CONFIG.get("tracking", {})
        self.camera_id = camera_id
        self.device = device
        self.half = half

        # Station ROI: only people inside it are tracked / get P-IDs.
        self.roi = None
        if roi is not None and len(roi) >= 3 and cfg.get("station_roi_only", True):
            self.roi = np.array(roi, dtype=np.int32).reshape(-1, 1, 2)

        # ---- tracker options: script defaults, then config.json ----
        self.args = _default_args()
        self.args.max_ids = cfg.get("max_ids", self.args.max_ids)
        self.args.device = device
        for key, value in cfg.get("overrides", {}).items():
            if not hasattr(self.args, key):
                raise ValueError(f"tracking.overrides: unknown option '{key}'")
            setattr(self.args, key, value)

        # ---- person model (separate YOLO instance: track() keeps its own state) ----
        if cfg.get("person_model"):
            weights = resolve_model_path(cfg["person_model"])
            self.person_class = cfg.get("person_class", 0)
        elif fallback_weights:
            weights = fallback_weights
            self.person_class = fallback_class
        else:
            raise ValueError("tracking.person_model is not set in config.json")
        self.model = YOLO(weights)

        # ---- appearance model (OSNet .pt or .onnx) ----
        if not cfg.get("reid_model"):
            raise ValueError("tracking.reid_model is not set in config.json")
        self.encoder = tp.Encoder(resolve_model_path(cfg["reid_model"]), device)

        # ---- fps: start value, then measured processing rate ----
        self.fps = float(cfg.get("fps", 10))
        self.auto_fps = cfg.get("auto_fps", True)
        self._last_t = None
        self._dt = None

        run_dir = Path(BASE_DIR) / "tracking_runtime"
        run_dir.mkdir(parents=True, exist_ok=True)
        self.yaml_path = run_dir / f"{camera_id}_botsort.yaml"
        tp.write_tracker_yaml(self.yaml_path, self.args, self.fps)

        log_dir = Path(BASE_DIR) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = open(log_dir / f"tracking_{camera_id}.txt", "a", buffering=1)
        self.print_events = cfg.get("print_events", True)

        self.mgr = None
        self.frame_idx = 0
        print(f"[INFO] {camera_id}: person tracking on, max_ids={self.args.max_ids}, "
              f"gallery={self.args.gallery_mode}, learn_s={self.args.learn_s}, "
              f"area={'station ROI' if self.roi is not None else 'full frame'}")

    def _in_roi(self, box):
        """Box centre or feet inside the station ROI."""
        x1, y1, x2, y2 = box
        for pt in (((x1 + x2) / 2, (y1 + y2) / 2), ((x1 + x2) / 2, y2)):
            if cv2.pointPolygonTest(self.roi, (float(pt[0]), float(pt[1])), False) >= 0:
                return True
        return False

    # ------------------------------------------------------------------ #
    def _log(self, fi, msg):
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{self.camera_id} frame {fi}] {msg}"
        self._log_file.write(line + "\n")
        if self.print_events:
            print(f"[TRACK] {line}")

    def _measure_fps(self):
        now = time.time()
        if self._last_t is not None:
            dt = now - self._last_t
            if 0 < dt < 5:  # ignore stream gaps
                self._dt = dt if self._dt is None else 0.95 * self._dt + 0.05 * dt
        self._last_t = now

    def reset(self):
        """Forget every P-ID (e.g. at a shift change: new people, closed set starts again)."""
        self.mgr = None
        predictor = getattr(self.model, "predictor", None)
        for t in (getattr(predictor, "trackers", None) or []):
            try:
                t.reset()
            except Exception:  # noqa: BLE001
                pass
        self._log(self.frame_idx, "=== RESET: all P-IDs forgotten ===")

    # ------------------------------------------------------------------ #
    def update(self, frame):
        if self.auto_fps:
            self._measure_fps()

        if self.mgr is None:
            h, w = frame.shape[:2]
            fps = float(np.clip(1.0 / self._dt, 1, 60)) if self._dt else self.fps
            self.mgr = tp.GlobalIDManager(fps, w, h, self.args, self._log)
        elif self.auto_fps and self._dt and self.frame_idx % 50 == 0:
            # Time-based settings (learn_s, verify_after_s, ...) follow the real rate.
            self.mgr.fps = float(np.clip(1.0 / self._dt, 1, 60))

        res = self.model.track(
            frame, persist=True, tracker=str(self.yaml_path),
            classes=[self.person_class], conf=self.args.conf, imgsz=self.args.imgsz,
            device=self.device, half=self.half, verbose=False,
        )[0]

        b = res.boxes
        if b is not None and b.id is not None and len(b):
            boxes = b.xyxy.cpu().numpy().astype(np.float32)
            lids = b.id.cpu().numpy().astype(int).tolist()
            confs = b.conf.cpu().numpy()
        else:
            boxes, lids, confs = np.zeros((0, 4), np.float32), [], np.zeros(0)

        # People outside the station ROI are ignored: no P-ID, no gallery, no slot used.
        if self.roi is not None and len(lids):
            keep = [i for i, bx in enumerate(boxes) if self._in_roi(bx)]
            boxes, confs = boxes[keep], confs[keep]
            lids = [lids[i] for i in keep]

        results = self.mgr.update(
            self.frame_idx, lids, boxes, confs, lambda bx: self.encoder(frame, bx)
        )
        self.frame_idx += 1

        return [
            {"gid": int(gid), "lid": int(lid), "state": state, "box": box,
             "conf": float(cf), "app_dist": float(d)}
            for (lid, gid, state, d), box, cf in zip(results, boxes, confs)
        ]