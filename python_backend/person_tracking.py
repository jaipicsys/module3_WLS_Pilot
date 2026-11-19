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

FILES WRITTEN (all inside  tracking_runtime/ , next to <camera>_botsort.yaml)
  <cam>_<stamp>_tracks.txt   one CSV row per detected box per frame
                             (same columns as the standalone script's *_tracks.txt)
  <cam>_<stamp>_events.txt   NEW / RELINK / MOVE / SWAP / UNLABEL / UNKNOWN / GALLERY lines
                             (same format as the standalone script's *_events.txt),
                             plus a "=== SUMMARY ===" block when the stream ends
  crops/<cam>_<stamp>/P<n>/  OPTIONAL clean person crops (config: tracking.save_crops_every)
The video is NOT written here (video_recorder.py already stores it in recordings/).

Optional keys in config.json -> "tracking":
  "save_crops_every": 30         save crops every N frames (0 = off). Use a multiple of 3.
  "save_crops_min_conf": 0.6     only confident detections
  "save_crops_max_per_id": 1000  cap per P-ID per session
  "log_segment_minutes": 60      start new tracks/events files this often (0 = never)
  "log_retention_days": 7        delete old tracks/events files after N days (0 = keep all)
"""

import re
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

import track_people_osnet_frozen as tp
from config_utils import BASE_DIR, CONFIG, resolve_model_path

_ARGS_LOCK = threading.Lock()

TRACKS_HEADER = ("frame,time_s,global_id,track_id,state,x1,y1,x2,y2,w,h,cx,cy,"
                 "foot_x,foot_y,conf,app_dist,next_id,next_dist,cls\n")


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


def _resolve_classes(spec, default, names):
    """Class ids from a config list that may hold ids (5) or names ("Inspection_Person")."""
    by_name = {str(v).lower(): int(k) for k, v in names.items()}
    out = []
    for c in (default if spec is None else spec):
        if isinstance(c, str) and not c.strip().isdigit():
            if c.strip().lower() not in by_name:
                raise ValueError(f"tracking class '{c}' is not in the person model: {names}")
            out.append(by_name[c.strip().lower()])
        else:
            cid = int(c)
            if cid not in {int(k) for k in names}:
                raise ValueError(f"tracking class id {cid} is not in the person model: {names}")
            out.append(cid)
    return list(dict.fromkeys(out))  # no duplicates, order kept


class PersonTracker:
    def __init__(self, camera_id, device, half, fallback_weights=None, fallback_class=0,
                 roi=None):
        cfg = CONFIG.get("tracking", {})
        self.camera_id = camera_id
        self.device = device
        # Match the independent script: YOLO inference uses FP32.
        self.half = False

        # Station ROI: only people inside it are tracked / get P-IDs.
        self.roi = None
        if roi is not None and len(roi) >= 3 and cfg.get("station_roi_only", True):
            self.roi = np.array(roi, dtype=np.int32).reshape(-1, 1, 2)

        # ---- tracker options: script defaults, then config.json ----
        self.args = _default_args()
        self.args.max_ids = cfg.get("max_ids", self.args.max_ids)
        self.args.max_insp_ids = cfg.get("max_insp_ids", self.args.max_insp_ids)  # pool I1, I2 ...
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

        # ---- which classes are tracked as people (default: only person_class, as before) ----
        # tracking.person_classes      e.g. ["Person", "Inspection_Person"] (names or ids)
        # tracking.non_operator_classes e.g. ["Inspection_Person"]: tracked and shown with a
        #     P-ID, but never bound to an operator seat by the station logic.
        _names = {int(k): str(v) for k, v in self.model.names.items()}
        self.person_classes = _resolve_classes(cfg.get("person_classes"), [self.person_class], _names)
        self.non_operator_classes = set(_resolve_classes(cfg.get("non_operator_classes"), [], _names))
        self._cls_votes = {}   # tracker id -> (recent class ids, last frame seen)
        # Debug: also show people OUTSIDE the station ROI in the video (thin box + "(out)").
        # Default False = as before; inspection persons are always shown.
        self.show_outside_roi = bool(cfg.get("show_outside_roi", False))
        print(f"[INFO] {camera_id}: tracking classes "
              f"{[f'{c}:{_names[c]}' for c in self.person_classes]}"
              + (f", non-operator {[_names[c] for c in sorted(self.non_operator_classes)]}"
                 if self.non_operator_classes else ""))

        # ---- appearance model (OSNet .pt or .onnx) ----
        if not cfg.get("reid_model"):
            raise ValueError("tracking.reid_model is not set in config.json")
        self.reid_path = resolve_model_path(cfg["reid_model"])
        self.encoder = tp.Encoder(self.reid_path, device)

        # ---- fps: start value, then measured processing rate ----
        self.fps = float(cfg.get("fps", 10))
        self.auto_fps = cfg.get("auto_fps", True)
        self._last_t = None
        self._dt = None

        run_dir = Path(BASE_DIR) / "tracking_runtime"
        run_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir = run_dir
        self.yaml_path = run_dir / f"{camera_id}_botsort.yaml"
        tp.write_tracker_yaml(self.yaml_path, self.args, self.fps)

        # wall-clock event log (one file per camera, appended)
        log_dir = Path(BASE_DIR) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = open(log_dir / f"tracking_{camera_id}.txt", "a", buffering=1)
        self.print_events = cfg.get("print_events", True)

        # Match the standalone script's ReID diagnostics on the output video.
        self.debug_overlay = cfg.get("debug_overlay", True)
        self.track_events = {}          # local track id -> (frame, reason)
        self.recent_events = deque(maxlen=6)
        self._ev_lock = threading.Lock()  # tracker thread writes, draw thread reads
        self._debug_tracks = []

        # ---- standalone-style log files (tracks / events) ----
        self.segment_s = float(cfg.get("log_segment_minutes", 60)) * 60
        self.retention_days = float(cfg.get("log_retention_days", 7))
        self._tracks_f = None
        self._events_f = None
        self._stem = None
        self._seg_start = 0.0
        self._open_logs()

        # ---- optional crop saving (for reviewing / retraining ReID) ----
        self.crop_every = int(cfg.get("save_crops_every", 0))
        self.crop_min_conf = float(cfg.get("save_crops_min_conf", 0.6))
        self.crop_max_per_id = int(cfg.get("save_crops_max_per_id", 1000))
        self._crop_session = None       # folder name, new for every new ID set
        self._crop_count = {}           # gid -> crops saved in this session

        self._lock = threading.RLock()
        self.mgr = None
        self.frame_idx = 0

        # Warm-up: first calls are slow (CUDA init); do them before the stream starts.
        _dummy = np.zeros((1080, 1920, 3), np.uint8)
        self.model.track(_dummy, persist=True, tracker=str(self.yaml_path),
                         classes=self.person_classes, conf=self.args.conf,
                         imgsz=self.args.imgsz, device=self.device,
                         half=self.half, verbose=False,
                         agnostic_nms=len(self.person_classes) > 1)
        self.encoder(_dummy, np.array([[100, 100, 200, 400]], np.float32))
        _pred = getattr(self.model, "predictor", None)
        for _t in (getattr(_pred, "trackers", None) or []):
            _t.reset()

        print(f"[INFO] {camera_id}: person tracking on, max_ids={self.args.max_ids}, "
              f"gallery={self.args.gallery_mode}, learn_s={self.args.learn_s}, "
              f"area={'station ROI' if self.roi is not None else 'full frame'}, "
              f"crops={'every %d frames' % self.crop_every if self.crop_every else 'off'}")
        print(f"[INFO] {camera_id}: tracking logs -> {self.run_dir}")

    # ------------------------------------------------------------------ #
    # log files
    # ------------------------------------------------------------------ #
    def _open_logs(self):
        """Open a fresh <cam>_<stamp>_tracks.txt / _events.txt pair."""
        for f in (self._tracks_f, self._events_f):
            if f is not None:
                try:
                    f.close()
                except Exception:  # noqa: BLE001
                    pass
        self._stem = f"{self.camera_id}_{time.strftime('%Y%m%d_%H%M%S')}"
        self._tracks_f = open(self.run_dir / f"{self._stem}_tracks.txt", "w", buffering=1)
        self._tracks_f.write(TRACKS_HEADER)
        self._events_f = open(self.run_dir / f"{self._stem}_events.txt", "w", buffering=1)
        self._seg_start = time.time()
        self._delete_old_logs()

    def _delete_old_logs(self):
        if self.retention_days <= 0:
            return
        limit = time.time() - self.retention_days * 86400
        for pat in (f"{self.camera_id}_*_tracks.txt", f"{self.camera_id}_*_events.txt"):
            for p in self.run_dir.glob(pat):
                try:
                    if p.stat().st_mtime < limit:
                        p.unlink()
                except OSError:
                    pass

    def _maybe_rotate_logs(self):
        if self.segment_s > 0 and time.time() - self._seg_start >= self.segment_s:
            self._open_logs()
            self._log_header()   # so each file starts with the settings that were used

    def _log_header(self):
        a, m = self.args, self.mgr
        self._log(self.frame_idx,
                  f"source={self.camera_id} {m.W}x{m.H}@{m.fps:.1f}fps "
                  f"tracker_yaml={self.yaml_path}")
        self._log(self.frame_idx,
                  f"reid={self.reid_path} gallery={a.gallery_mode} gallery_size={a.gallery_size} "
                  f"assign_app_max={a.assign_app_max} keep_dist={a.keep_dist} "
                  f"unlabel_dist={a.unlabel_dist} verify={a.verify_votes}/{a.verify_window} "
                  f"learn_s={a.learn_s} verify_after_s={a.verify_after_s} "
                  f"stable={a.stable_s}s/{a.stable_margin} partial_h={a.partial_h_ratio} "
                  f"max_radius={a.max_radius} confirm_min_conf={a.confirm_min_conf}")

    def _write_tracks(self, fi, results, boxes, confs, clss=None):
        """Same rows as track_people_osnet_frozen.py: every detected box (not only the ROI)."""
        self._maybe_rotate_logs()
        ts = fi / self.mgr.fps
        clss = clss if clss is not None else [self.person_classes[0]] * len(results)
        for (lid, gid, state, d), box, cf, cl in zip(results, boxes, confs, clss):
            x1, y1, x2, y2 = box
            fx, fy = (x1 + x2) / 2.0, y2
            nid, nd = -1, -1.0
            if gid > 0:
                lc = self.mgr.people[gid].last_check
                if lc and lc[0] == fi:
                    _, _, nid, nd = lc
                    nid = -1 if nid is None else nid
            self._tracks_f.write(
                f"{fi},{ts:.3f},{gid},{lid},{state},{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f},"
                f"{x2 - x1:.1f},{y2 - y1:.1f},{(x1 + x2) / 2:.1f},{(y1 + y2) / 2:.1f},"
                f"{fx:.1f},{fy:.1f},{cf:.3f},{d:.3f},{nid},{nd:.3f},{cl}\n")

    def write_summary(self):
        """Same '=== SUMMARY ===' block the standalone script writes when it stops."""
        with self._lock:
            if self.mgr is None:
                return
            fi, fps = self.frame_idx, self.mgr.fps
            self._log(fi, "=== SUMMARY ===")
            for p in sorted(self.mgr.people.values(), key=lambda p: p.gid):
                self._log(fi, f"{tp.pid_name(p.gid)}: first={p.first_frame / fps:.1f}s "
                              f"last={p.last_frame / fps:.1f}s frames={p.frames_seen} "
                              f"relinks={p.relinks} swaps/moves={p.reassigns} "
                              f"path={p.path_px:.0f}px gallery={len(p.gallery)}"
                              f"{' (frozen)' if p.frozen else ''}")

    # ------------------------------------------------------------------ #
    # crops
    # ------------------------------------------------------------------ #
    def _save_crops(self, fi, frame, results, boxes, confs):
        """Save clean crops of people that carry a P-ID. Crops go in a folder per ID SESSION,
        because P-IDs restart after a shift change / restart (P1 may be a different person).
        The labels are the system's OWN guesses: review them before using them for training."""
        if not self.crop_every or fi % self.crop_every:
            return
        H, W = frame.shape[:2]
        n = len(boxes)
        ious = tp.iou_matrix(boxes, boxes) if n > 1 else None
        if ious is not None:
            np.fill_diagonal(ious, 0)
        for k, ((lid, gid, state, d), box, cf) in enumerate(zip(results, boxes, confs)):
            # confident, already-labelled, and its look really matches that ID
            if gid <= 0 or state != "tracked" or cf < self.crop_min_conf:
                continue
            if not (0 <= d <= self.args.assign_app_max):
                continue
            if ious is not None and ious[k].max() > 0.05:    # nobody overlapping
                continue
            if self._crop_count.get(gid, 0) >= self.crop_max_per_id:
                continue
            x1, y1, x2, y2 = [int(v) for v in box]
            if x1 < 3 or y1 < 3 or x2 > W - 3 or y2 > H - 3:  # not cut by the frame edge
                continue
            if x2 - x1 < 40 or y2 - y1 < 100:
                continue
            folder = self.run_dir / "crops" / self._crop_session / tp.pid_name(gid)
            folder.mkdir(parents=True, exist_ok=True)
            name = f"f{fi:07d}_t{lid}_d{d:.2f}.jpg"
            cv2.imwrite(str(folder / name), frame[y1:y2, x1:x2])
            self._crop_count[gid] = self._crop_count.get(gid, 0) + 1

    # ------------------------------------------------------------------ #
    def _in_roi(self, box):
        """Box centre or feet inside the station ROI."""
        x1, y1, x2, y2 = box
        for pt in (((x1 + x2) / 2, (y1 + y2) / 2), ((x1 + x2) / 2, y2)):
            if cv2.pointPolygonTest(self.roi, (float(pt[0]), float(pt[1])), False) >= 0:
                return True
        return False

    def _log(self, fi, msg):
        fps = self.mgr.fps if self.mgr is not None else self.fps
        # wall-clock log (logs/tracking_<cam>.txt)
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{self.camera_id} frame {fi}] {msg}"
        self._log_file.write(line + "\n")
        # standalone-style log (tracking_runtime/<cam>_<stamp>_events.txt)
        self._events_f.write(f"[frame {fi:6d} | {fi / fps:8.2f}s] {msg}\n")
        # Same event filtering and local-track extraction as frozen.py.
        first = msg.split()[0] if msg.split() else ""
        if first in ("NEW", "RELINK", "MOVE", "SWAP", "UNLABEL", "UNKNOWN"):
            with self._ev_lock:
                self.recent_events.append((fi, msg))
                match = re.search(r"tracks? (\d+)(?:,(\d+))?", msg)
                if match:
                    for track_id in match.groups():
                        if track_id:
                            self.track_events[int(track_id)] = (fi, msg)
        if self.print_events:
            print(f"[TRACK] {line}")

    def draw_debug(self, frame, tracks=None):
        """Draw the standalone frozen.py ReID diagnostics on the output frame, plus
        'tracker frame N' (the same N as in *_events.txt / *_tracks.txt) so a moment in the
        recording can be matched with the logs. Pass the tracks that belong to this frame."""
        if not self.debug_overlay or self.mgr is None:
            return
        tracks = tracks if tracks is not None else self._debug_tracks
        fi = tracks[0].get("fi", self.frame_idx - 1) if tracks else self.frame_idx - 1
        label = f"tracker frame {fi}"
        cv2.putText(frame, label, (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 6, cv2.LINE_AA)
        cv2.putText(frame, label, (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 2, cv2.LINE_AA)
        if not tracks:
            return
        results = [(t["lid"], t["gid"], t["state"], t["app_dist"]) for t in tracks]
        boxes = np.asarray([t["box"] for t in tracks], dtype=np.float32)
        confs = np.asarray([t["conf"] for t in tracks], dtype=np.float32)
        with self._ev_lock:
            track_events = dict(self.track_events)
            recent_events = list(self.recent_events)
        try:
            tp.draw_debug(frame, fi, results, boxes, confs, self.mgr,
                          self.args, track_events, recent_events)
        except RuntimeError:
            pass  # tracker thread changed its state while drawing: skip the overlay for this frame

    def _measure_fps(self):
        now = time.time()
        if self._last_t is not None:
            dt = now - self._last_t
            if 0 < dt < 5:  # ignore stream gaps
                self._dt = dt if self._dt is None else 0.95 * self._dt + 0.05 * dt
        self._last_t = now

    def reset(self):
        with self._lock:
            self._reset()

    def _reset(self):
        """Forget every P-ID (e.g. at a shift change: new people, closed set starts again)."""
        self.write_summary()                 # close the old ID set in the events file
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
        with self._lock:
            return self._update(frame)

    def _update(self, frame):
        if self.auto_fps:
            self._measure_fps()

        if self.mgr is None:
            h, w = frame.shape[:2]
            fps = float(np.clip(1.0 / self._dt, 1, 60)) if self._dt else self.fps
            self.mgr = tp.GlobalIDManager(fps, w, h, self.args, self._log)
            self._sessions = getattr(self, "_sessions", 0) + 1
            self._crop_session = (f"{self.camera_id}_{time.strftime('%Y%m%d_%H%M%S')}"
                                  f"_s{self._sessions}")
            self._crop_count = {}
            self._log_header()
        elif self.auto_fps and self._dt and self.frame_idx % 50 == 0:
            # Time-based settings (learn_s, verify_after_s, ...) follow the real rate.
            self.mgr.fps = float(np.clip(1.0 / self._dt, 1, 60))

        res = self.model.track(
            frame, persist=True, tracker=str(self.yaml_path),
            classes=self.person_classes, conf=self.args.conf, imgsz=self.args.imgsz,
            device=self.device, half=self.half, verbose=False,
            # one human can be detected as two classes: keep only the stronger box
            agnostic_nms=len(self.person_classes) > 1,
        )[0]

        b = res.boxes
        if b is not None and b.id is not None and len(b):
            boxes = b.xyxy.cpu().numpy().astype(np.float32)
            lids = b.id.cpu().numpy().astype(int).tolist()
            confs = b.conf.cpu().numpy()
            clss = b.cls.cpu().numpy().astype(int).tolist()
        else:
            boxes, lids, confs, clss = np.zeros((0, 4), np.float32), [], np.zeros(0), []

        # Mirror the independent script: all detected people reach GlobalIDManager.
        # Apply Station ROI only to the returned tracks used by station/operator logic.
        fi = self.frame_idx
        stable = [self._track_class(int(l), int(c), fi) for l, c in zip(lids, clss)]
        # Inspection persons have their own ID pool (I1, I2 ...): the manager only ever gives a
        # track an ID of its own pool, so an inspection person can never receive a P-ID.
        groups = [1 if c in self.non_operator_classes else 0 for c in stable]
        all_results = self.mgr.update(
            fi, lids, boxes, confs, lambda bx: self.encoder(frame, bx), groups=groups
        )
        self._write_tracks(fi, all_results, boxes, confs, stable)
        try:
            self._save_crops(fi, frame, all_results, boxes, confs)
        except Exception as exc:  # noqa: BLE001  (crops must never break tracking)
            print(f"[WARNING] {self.camera_id}: saving crops failed: {exc}")
        self.frame_idx += 1

        visible = []
        for (lid, gid, state, d), box, cf, cl in zip(all_results, boxes, confs, stable):
            insp = cl in self.non_operator_classes
            inside = self.roi is None or self._in_roi(box)
            # Station logic only sees people inside the ROI - except inspection persons (always
            # shown with their P-ID, never bound to an operator) and, if enabled, everybody.
            if not inside and not insp and not self.show_outside_roi:
                continue
            visible.append(
                {"gid": int(gid), "lid": int(lid), "state": state, "box": box,
                 "conf": float(cf), "app_dist": float(d), "fi": fi,
                 "cls": cl, "inspection": insp, "outside": not inside}
            )
        self._debug_tracks = visible
        return visible

    def _track_class(self, lid, cls, fi):
        """Class of a tracker id = majority of its last 15 detections, so a person who flickers
        between 'Person' and 'Inspection_Person' does not flip between operator / non-operator."""
        if len(self.person_classes) == 1:
            return cls
        votes, _ = self._cls_votes.get(lid, (deque(maxlen=15), fi))
        votes.append(cls)
        self._cls_votes[lid] = (votes, fi)
        if fi % 500 == 0:  # forget tracker ids that disappeared long ago
            for k in [k for k, (_, f) in self._cls_votes.items() if fi - f > 2000]:
                del self._cls_votes[k]
        return max(set(votes), key=lambda c: (list(votes).count(c), c == cls))

    def set_source_fps(self, fps):
        """Use the same source-FPS rule as the standalone script."""
        try:
            fps = float(fps)
        except (TypeError, ValueError):
            fps = 0.0
        if not 1 <= fps <= 120:
            fps = 25.0
        self.fps = fps
        self.auto_fps = False
        tp.write_tracker_yaml(self.yaml_path, self.args, self.fps)
        if self.mgr is not None:
            self.mgr.fps = self.fps