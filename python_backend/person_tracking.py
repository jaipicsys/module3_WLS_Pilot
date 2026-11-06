"""
Person tracking for the operator logic (one instance per camera).

This does NOT re-implement the tracking. A separate PROCESS runs the same loop as
main() of track_people_osnet_frozen.py, with the same ingredients:

  * its own RTSP connection through tp.RTSPReader (latest frame, buffer 1)
  * fps taken from the stream (25 if unknown), written into the BoT-SORT yaml
  * model.track(frame, persist=True, ...) with the script's defaults
    (no half precision, device=None, imgsz 960, conf 0.30)
  * tp.GlobalIDManager + tp.Encoder (OSNet) with the script's defaults,
    fixed fps (no auto fps)

Being a separate process, it gets its own Python interpreter (no GIL sharing with
detection / pose / drawing / recording in the backend), like the standalone run.

The backend side (this class) only receives the result:
  latest()      -> list of {"gid", "lid", "state", "box", "conf", "app_dist"}
                   gid -1 = tracker sees a person, no P-ID trusted yet
  is_stable()   -> True once a P-ID's gallery is learnt (used for operator binding)
  reset()       -> forget all P-IDs (shift change)
  start()/stop()

config.json "tracking" keys used: person_model, reid_model, person_class, max_ids,
overrides (any option of track_people_osnet_frozen.parse_args, e.g. learn_s),
print_events. The RTSP url comes from rtsp_urls[camera_id].

track_people_osnet_frozen.py and export_osnet.py must sit next to this file.
"""

import multiprocessing as mp
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from config_utils import BASE_DIR, CONFIG, resolve_model_path


# =========================================================================== #
#  Child process: the standalone script's main loop, without drawing/writing
# =========================================================================== #
def _worker(camera_id, source, cfg, out_q, cmd_q, parent_pid):
    import cv2
    from ultralytics import YOLO

    import track_people_osnet_frozen as tp

    # ---- the script's own defaults (no command line) ----
    saved = sys.argv
    sys.argv = [saved[0] if saved else "tracker"]
    try:
        args = tp.parse_args()
    finally:
        sys.argv = saved

    args.source = source
    args.weights = resolve_model_path(cfg["person_model"])
    args.reid_model = resolve_model_path(cfg["reid_model"])
    args.person_class = cfg.get("person_class", 0)
    args.max_ids = cfg.get("max_ids", args.max_ids)
    for key, value in cfg.get("overrides", {}).items():
        if not hasattr(args, key):
            raise ValueError(f"tracking.overrides: unknown option '{key}'")
        setattr(args, key, value)
    args.device = None  # exactly like the standalone run

    # ---- log (same format as before: logs/tracking_<cam>.txt) ----
    log_dir = Path(BASE_DIR) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(log_dir / f"tracking_{camera_id}.txt", "a", buffering=1)
    print_events = cfg.get("print_events", True)

    def log(fi, msg):
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{camera_id} frame {fi}] {msg}"
        log_file.write(line + "\n")
        if print_events:
            print(f"[TRACK] {line}", flush=True)

    def parent_alive():
        return os.getppid() == parent_pid

    def open_reader():
        """Open the stream the way the standalone does; retry until it works."""
        while parent_alive():
            try:
                r = tp.RTSPReader(source)
                ok, _ = r.read()
                if ok:
                    return r
                r.release()
            except Exception as e:  # noqa: BLE001
                log(0, f"cannot open {source}: {e}")
            time.sleep(3)
        return None

    reader = open_reader()
    if reader is None:
        return
    fps = reader.get(cv2.CAP_PROP_FPS) or 0
    fps = fps if 1 <= fps <= 120 else 25.0
    ok, frame = reader.read()
    while not ok:
        ok, frame = reader.read()
    H, W = frame.shape[:2]

    run_dir = Path(BASE_DIR) / "tracking_runtime"
    run_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = run_dir / f"{camera_id}_botsort.yaml"
    tp.write_tracker_yaml(yaml_path, args, fps)

    model = YOLO(args.weights)
    encoder = tp.Encoder(args.reid_model, args.device)
    mgr = tp.GlobalIDManager(fps, W, H, args, log)

    log(0, f"tracker process: source={source} {W}x{H}@{fps:.1f}fps max_ids={args.max_ids} "
           f"gallery={args.gallery_mode} learn_s={args.learn_s}")

    fi, t100 = 0, time.time()
    while parent_alive():
        # ---- commands from the backend ----
        try:
            while True:
                cmd = cmd_q.get_nowait()
                if cmd == "stop":
                    reader.release()
                    return
                if cmd == "reset":
                    mgr = tp.GlobalIDManager(fps, W, H, args, log)
                    predictor = getattr(model, "predictor", None)
                    for t in (getattr(predictor, "trackers", None) or []):
                        try:
                            t.reset()
                        except Exception:  # noqa: BLE001
                            pass
                    log(fi, "=== RESET: all P-IDs forgotten ===")
        except queue.Empty:
            pass

        ok, frame = reader.read()
        if not ok:
            log(fi, "stream lost, reconnecting (P-IDs are kept)")
            reader.release()
            reader = open_reader()
            if reader is None:
                return
            continue

        # ---- identical to the standalone loop ----
        res = model.track(frame, persist=True, tracker=str(yaml_path), classes=[args.person_class],
                          conf=args.conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
        b = res.boxes
        if b is not None and b.id is not None and len(b):
            boxes = b.xyxy.cpu().numpy().astype(np.float32)
            lids = b.id.cpu().numpy().astype(int).tolist()
            confs = b.conf.cpu().numpy()
        else:
            boxes, lids, confs = np.zeros((0, 4), np.float32), [], np.zeros(0)

        results = mgr.update(fi, lids, boxes, confs, lambda bx: encoder(frame, bx))
        fi += 1

        if fi % 100 == 0:
            now = time.time()
            log(fi, f"processing fps = {100.0 / (now - t100):.1f}")
            t100 = now

        # ---- hand the result to the backend (drop it if the backend is behind) ----
        msg = {
            "stable": {g: (p.frozen, p.frames_seen, p.local_id is not None)
                       for g, p in mgr.people.items()},
            "mgr_fps": float(mgr.fps),
            "tracks": [
                {"gid": int(gid), "lid": int(lid), "state": state, "box": box,
                 "conf": float(cf), "app_dist": float(d)}
                for (lid, gid, state, d), box, cf in zip(results, boxes, confs)
            ],
        }
        try:
            out_q.put_nowait(msg)
        except queue.Full:
            pass

    reader.release()


# =========================================================================== #
#  Backend side
# =========================================================================== #
class PersonTracker:
    _target = staticmethod(_worker)  # replaced only in tests

    def __init__(self, camera_id, device=None, half=None, fallback_weights=None,
                 fallback_class=0, roi=None):
        # `device` and `half` are accepted for compatibility but unused: the tracker
        # process runs with the standalone script's own defaults.
        cfg = dict(CONFIG.get("tracking", {}))
        if not cfg.get("person_model") and fallback_weights:
            cfg["person_model"] = fallback_weights
            cfg["person_class"] = fallback_class
        if not cfg.get("person_model"):
            raise ValueError("tracking.person_model is not set in config.json")
        if not cfg.get("reid_model"):
            raise ValueError("tracking.reid_model is not set in config.json")
        resolve_model_path(cfg["person_model"])  # fail early if a model file is missing
        resolve_model_path(cfg["reid_model"])

        source = CONFIG.get("rtsp_urls", {}).get(camera_id)
        if not source:
            raise ValueError(f"No rtsp url for camera '{camera_id}' in config.json")

        self.camera_id = camera_id
        self.cfg = cfg
        self.source = source

        # Station ROI: only kept for drawing.
        self.roi = None
        if roi is not None and len(roi) >= 3:
            self.roi = np.array(roi, dtype=np.int32).reshape(-1, 1, 2)

        self._ctx = mp.get_context("spawn")  # CUDA needs spawn, not fork
        self._proc = None
        self._out_q = None
        self._cmd_q = None
        self._thread = None
        self._stop_flag = False

        self._lock = threading.Lock()
        self._tracks, self._stable, self._mgr_fps, self._time = [], {}, 25.0, 0.0

        print(f"[INFO] {camera_id}: person tracking = standalone loop in its own process, "
              f"max_ids={cfg.get('max_ids')}, source={source}")

    # ---- lifecycle ------------------------------------------------------- #
    def _spawn(self):
        self._out_q = self._ctx.Queue(maxsize=4)
        self._cmd_q = self._ctx.Queue()
        self._proc = self._ctx.Process(
            target=self._target,
            args=(self.camera_id, self.source, self.cfg, self._out_q, self._cmd_q, os.getpid()),
            daemon=True,
            name=f"tracker-{self.camera_id}",
        )
        self._proc.start()

    def start(self, reader=None):
        """Start the tracker process. `reader` is ignored: it opens its own RTSP connection."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_flag = False
        self._spawn()
        self._thread = threading.Thread(
            target=self._recv_loop, daemon=True, name=f"tracker-recv-{self.camera_id}"
        )
        self._thread.start()

    def stop(self):
        self._stop_flag = True
        proc = self._proc
        if proc is not None:
            try:
                self._cmd_q.put("stop")
            except Exception:  # noqa: BLE001
                pass
            proc.join(timeout=5)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5)
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=5)
        self._thread = None
        self._proc = None

    def _recv_loop(self):
        while not self._stop_flag:
            try:
                msg = self._out_q.get(timeout=0.5)
            except queue.Empty:
                proc = self._proc
                if proc is not None and not proc.is_alive() and not self._stop_flag:
                    print(f"[WARNING] {self.camera_id}: tracker process stopped "
                          f"(exit code {proc.exitcode}). Restarting in 3 s...")
                    time.sleep(3)
                    if not self._stop_flag:
                        self._spawn()
                continue
            except (EOFError, OSError):
                time.sleep(0.2)
                continue

            try:  # keep only the newest
                while True:
                    msg = self._out_q.get_nowait()
            except queue.Empty:
                pass

            with self._lock:
                self._tracks = msg["tracks"]
                self._stable = msg["stable"]
                self._mgr_fps = msg["mgr_fps"]
                self._time = time.time()

    # ---- used by logics.py ----------------------------------------------- #
    def latest(self, max_age=2.0):
        """Newest tracks ([] if none yet or older than max_age seconds)."""
        with self._lock:
            if time.time() - self._time > max_age:
                return []
            return self._tracks

    def is_stable(self, gid, min_seen_s=20.0, require_frozen=False):
        """True when the P-ID is linked to a live track and its gallery is learnt enough."""
        with self._lock:
            info = self._stable.get(gid)
            fps = self._mgr_fps
        if info is None:
            return False
        frozen, frames_seen, linked = info
        if not linked:
            return False
        if require_frozen:
            return frozen
        return frozen or frames_seen >= min_seen_s * fps

    def reset(self):
        """Forget every P-ID (e.g. at a shift change)."""
        with self._lock:
            self._tracks, self._stable = [], {}
        if self._cmd_q is not None:
            self._cmd_q.put("reset")