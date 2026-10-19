import os
import re
import time
from datetime import datetime

import cv2
import numpy as np
import torch
from ultralytics import YOLO

import operator_db
from config_utils import (
    BASE_DIR,
    CONFIG,
    find_station_for_camera,
    get_shift_and_break,
    resolve_model_path,
)

ACTIVE = "active_work"
IDLE = "idle"
AWAY = "away"

REASON_NO_TOUCH = "Wrist not on towel"
REASON_AWAY = "Left station area"

# COCO keypoints: left wrist, right wrist
WRISTS = [9, 10]

FONT = cv2.FONT_HERSHEY_SIMPLEX

OBJECT_COLORS = {
    "towel": (255, 160, 0),
    "closed_box": (0, 165, 255),
    "trolly_box": (255, 0, 200),
    "yellow_person": (0, 255, 255),
}

COLOR_ACTIVE = (0, 200, 0)
COLOR_IDLE = (0, 165, 255)
COLOR_STATION = (255, 255, 0)
COLOR_PENDING = (200, 200, 200)
COLOR_IGNORED = (130, 130, 130)


def _cam_number(camera_id):
    digits = re.sub(r"\D", "", str(camera_id))
    return int(digits) if digits else None


def _poly(points):
    return np.array(points, dtype=np.int32).reshape(-1, 1, 2)


def _inside(poly, point):
    return cv2.pointPolygonTest(
        poly, (float(point[0]), float(point[1])), False
    ) >= 0


class OperatorStatus:
    """Debounced (state, reason) and open DB row for ONE tracked person."""

    def __init__(self, now):
        self.key = None
        self.since = None
        self.candidate = None
        self.candidate_since = None
        self.segment_id = None
        self.first_seen = now
        self.last_seen = now
        self.last_touch = None

    @property
    def status(self):
        return self.key[0] if self.key else None


class FrameLogic:
    """
    ByteTrack ids in monitor_ids are checked, everyone else is ignored.
      wrist on towel                   -> ACTIVE
      no wrist on towel for 3 seconds  -> IDLE
      id not inside the station ROI    -> AWAY
    """

    def __init__(self, camera_id):
        self.camera_id = camera_id

        found = find_station_for_camera(camera_id)
        if found is None:
            raise ValueError(f"No station configured for camera '{camera_id}'")
        self.line_id, self.line, self.station_id, self.station = found

        if not self.station.get("roi"):
            raise ValueError(f"Station {self.station_id} has no 'roi' in config.json")
        self.station_roi = _poly(self.station["roi"])

        cfg = CONFIG.get("operator_status", {})

        tracker = cfg.get("tracker", "bytetrack.yaml")
        local_tracker = os.path.join(BASE_DIR, tracker)
        self.tracker = local_tracker if os.path.exists(local_tracker) else tracker

        self.monitor_ids = set(cfg.get("monitor_ids", []))   # empty = everyone
        self.person_conf = cfg.get("person_conf", 0.3)
        self.pose_conf = cfg.get("pose_conf", 0.5)
        self.wrist_conf = cfg.get("wrist_conf", 0.3)
        self.towel_name = cfg.get("towel_class", "Towel").lower()
        self.towel_conf = cfg.get("towel_conf", 0.3)
        self.towel_margin = cfg.get("towel_margin", 0.05)
        self.idle_after = cfg.get("idle_after_seconds", 3)
        self.debounce = cfg.get("debounce_seconds", 1)
        self.away_seconds = cfg.get("away_seconds", 5)
        self.forget_seconds = cfg.get("forget_seconds", 120)
        self.ignore_names = [n.lower() for n in cfg.get("ignore_classes", [])]
        self.draw = CONFIG.get("enable_display", False)

        device = CONFIG.get("device", "auto")
        if device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.half = self.device != "cpu"

        if self.device == "cpu":
            print(f"[WARNING] {camera_id}: running on CPU (slow). "
                  f"CUDA available: {torch.cuda.is_available()}")
        else:
            print(f"[INFO] {camera_id}: running on {self.device} "
                  f"({torch.cuda.get_device_name(0)})")

        op_cfg = CONFIG["operations"][self.station["operation"]]
        self.det_conf = op_cfg.get("conf_thresh", 0.6)
        self.detect_conf = min(self.det_conf, self.person_conf, self.towel_conf)

        self.det_model = YOLO(resolve_model_path(op_cfg["model"]))
        self.pose_model = YOLO(resolve_model_path(CONFIG["pose_model"]))

        self.names = self.det_model.names
        lower_names = {i: n.lower() for i, n in self.names.items()}

        person_ids = [i for i, n in lower_names.items() if n == "person"]
        if not person_ids:
            raise ValueError(f"'Person' class not found in model: {self.names}")
        self.person_class = person_ids[0]

        if self.towel_name not in lower_names.values():
            raise ValueError(
                f"Towel class '{self.towel_name}' not found in model: {self.names}"
            )

        unknown = [n for n in self.ignore_names if n not in lower_names.values()]
        if unknown:
            raise ValueError(
                f"ignore_classes {unknown} not found in model: {self.names}"
            )
        ignore_ids = {i for i, n in lower_names.items() if n in self.ignore_names}
        self.detect_classes = [i for i in self.names if i not in ignore_ids]

        print(f"[INFO] {camera_id}: monitoring ids "
              f"{sorted(self.monitor_ids) if self.monitor_ids else 'ALL'}")

        self.operators = {}     # track id -> OperatorStatus

    # ---------------- main entry ----------------

    def process(self, frame):
        now = time.time()
        persons, towels, objects = self._detect(frame)

        self._check_wrists(persons, towels)
        self._update_operators(persons, now)

        if self.draw:
            self._draw(frame, persons, towels, objects)

        return frame

    # ---------------- detection ----------------

    @staticmethod
    def _anchor(box):
        x1, y1, x2, y2 = box
        return (float((x1 + x2) / 2), float(y2))

    def _monitored(self, tid):
        return not self.monitor_ids or tid in self.monitor_ids

    def _detect(self, frame):
        result = self.det_model.track(
            frame,
            persist=True,
            tracker=self.tracker,
            conf=self.detect_conf,
            classes=self.detect_classes,
            device=self.device,
            half=self.half,
            verbose=False,
        )[0]

        persons, towels, objects = [], [], []

        boxes = result.boxes
        if boxes is not None and len(boxes) > 0:
            xyxy = boxes.xyxy.cpu().numpy()
            classes = boxes.cls.int().cpu().tolist()
            confs = boxes.conf.cpu().numpy()
            ids = (
                boxes.id.int().cpu().tolist()
                if boxes.id is not None
                else [None] * len(classes)
            )

            for box, cls, conf, tid in zip(xyxy, classes, confs, ids):
                name = self.names[cls]

                if cls == self.person_class:
                    if tid is None or conf < self.person_conf:
                        continue
                    if not _inside(self.station_roi, self._anchor(box)):
                        continue
                    persons.append({
                        "id": tid, "box": box,
                        "monitored": self._monitored(tid),
                        "kxy": None, "kconf": None, "touching": False,
                    })
                elif name.lower() == self.towel_name:
                    if conf >= self.towel_conf:
                        towels.append({
                            "box": box, "conf": float(conf), "touched": False,
                        })
                elif conf >= self.det_conf:
                    objects.append({"name": name, "conf": float(conf), "box": box})

        # Pose only for monitored people
        for p in persons:
            if p["monitored"]:
                p["kxy"], p["kconf"] = self._pose_on_crop(frame, p["box"])

        return persons, towels, objects

    def _pose_on_crop(self, frame, box):
        """Pose of ONE person; with overlap, take the pose nearest to this box."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = box
        pad_x, pad_y = (x2 - x1) * 0.1, (y2 - y1) * 0.1
        cx1, cy1 = int(max(0, x1 - pad_x)), int(max(0, y1 - pad_y))
        cx2, cy2 = int(min(w, x2 + pad_x)), int(min(h, y2 + pad_y))

        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return None, None

        res = self.pose_model.predict(
            crop,
            conf=self.pose_conf,
            device=self.device,
            half=self.half,
            verbose=False,
        )[0]

        if res.keypoints is None or res.boxes is None or len(res.boxes) == 0:
            return None, None

        ox = (x1 + x2) / 2 - cx1
        oy = (y1 + y2) / 2 - cy1
        pb = res.boxes.xyxy.cpu().numpy()
        centres = np.stack(
            [(pb[:, 0] + pb[:, 2]) / 2, (pb[:, 1] + pb[:, 3]) / 2], axis=1
        )
        best = int(np.argmin(np.hypot(centres[:, 0] - ox, centres[:, 1] - oy)))

        xy = res.keypoints.xy[best].cpu().numpy() + np.array([cx1, cy1])
        conf = (
            res.keypoints.conf[best].cpu().numpy()
            if res.keypoints.conf is not None
            else np.ones(len(xy))
        )
        return xy, conf

    # ---------------- wrist on towel ----------------

    def _check_wrists(self, persons, towels):
        for p in persons:
            if not p["monitored"] or p["kxy"] is None:
                continue

            margin = (p["box"][3] - p["box"][1]) * self.towel_margin

            for k in WRISTS:
                if p["kconf"][k] <= self.wrist_conf:
                    continue
                wx, wy = p["kxy"][k]

                for t in towels:
                    tx1, ty1, tx2, ty2 = t["box"]
                    if (tx1 - margin <= wx <= tx2 + margin
                            and ty1 - margin <= wy <= ty2 + margin):
                        p["touching"] = True
                        t["touched"] = True

    # ---------------- active / idle / away ----------------

    def _decide(self, op, now):
        if op.last_touch is not None and now - op.last_touch <= self.idle_after:
            return ACTIVE, None
        ref = op.last_touch if op.last_touch is not None else op.first_seen
        if now - ref >= self.idle_after:
            return IDLE, REASON_NO_TOUCH
        return None

    def _update_operators(self, persons, now):
        present = set()

        for p in persons:
            if not p["monitored"]:
                continue

            tid = p["id"]
            present.add(tid)

            op = self.operators.get(tid)
            if op is None:
                op = self.operators[tid] = OperatorStatus(now)
            elif op.status == AWAY or now - op.last_seen > self.away_seconds:
                op.first_seen = now
                op.last_touch = None

            op.last_seen = now
            if p["touching"]:
                op.last_touch = now

            key = self._decide(op, now)
            if key is not None:
                self._update_person(tid, op, key, now)

        for tid in list(self.operators):
            if tid in present:
                continue

            op = self.operators[tid]
            gap = now - op.last_seen

            if gap >= self.away_seconds and op.key is not None and op.status != AWAY:
                self._commit_person(tid, op, (AWAY, REASON_AWAY), op.last_seen)

            if gap >= self.forget_seconds or (gap >= self.away_seconds and op.key is None):
                self._close_person(tid, op, now)
                del self.operators[tid]

    def _update_person(self, tid, op, key, now):
        if op.key is None:
            self._commit_person(tid, op, key, now)
            return

        if key == op.key:
            op.candidate = None
            return

        if key != op.candidate:
            op.candidate = key
            op.candidate_since = now
            return

        if now - op.candidate_since >= self.debounce:
            self._commit_person(tid, op, key, op.candidate_since)

    def _commit_person(self, tid, op, key, start_ts):
        state, reason = key
        if op.since is not None:
            start_ts = max(start_ts, op.since)
        print(f"[STATUS] {self.camera_id} P{tid}: {op.key} -> {key}")

        try:
            if op.segment_id is not None:
                operator_db.close_segment(
                    op.segment_id,
                    self._iso(start_ts),
                    start_ts - op.since,
                )

            op.segment_id = operator_db.open_segment(
                self._build_row(state, reason, datetime.fromtimestamp(start_ts), tid)
            )
        except Exception as e:
            print(f"[ERROR] operator_status write failed: {e}")

        op.key = key
        op.since = start_ts
        op.candidate = None

    def _close_person(self, tid, op, end_ts):
        if op.segment_id is None:
            return
        try:
            operator_db.close_segment(
                op.segment_id, self._iso(end_ts), end_ts - op.since
            )
            print(f"[STATUS] {self.camera_id} P{tid}: closed")
        except Exception as e:
            print(f"[ERROR] operator_status close failed: {e}")

    @staticmethod
    def _iso(ts):
        return datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")

    def _build_row(self, state, reason, start_dt, tid):
        shift, brk = get_shift_and_break(self.line, start_dt)
        return {
            "line_id": self.line_id,
            "product_name": self.line.get("product_name"),
            "shift_id": shift["shift_id"] if shift else None,
            "shift_timings": shift["timings"] if shift else None,
            "break_name": brk["break_name"] if brk else None,
            "break_timings": brk["timings"] if brk else None,
            "operation": self.station.get("operation"),
            "station_name": self.station.get("station_name"),
            "cam_id": _cam_number(self.camera_id),
            "start_time": self._iso(start_dt.timestamp()),
            "status": state,
            "reasons": reason,
            "operator_id": f"P{tid}",
            "plant": CONFIG.get("plant"),
        }

    # ---------------- drawing ----------------

    def _draw(self, frame, persons, towels, objects):
        cv2.polylines(frame, [self.station_roi], True, COLOR_STATION, 4)

        for o in objects:
            x1, y1, x2, y2 = map(int, o["box"])
            color = OBJECT_COLORS.get(o["name"].lower(), (200, 200, 0))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        for t in towels:
            x1, y1, x2, y2 = map(int, t["box"])
            color = COLOR_ACTIVE if t["touched"] else OBJECT_COLORS["towel"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5 if t["touched"] else 2)

        for p in persons:
            tid = p["id"]
            x1, y1, x2, y2 = map(int, p["box"])

            if not p["monitored"]:
                cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_IGNORED, 2)
                cv2.putText(frame, f"ID {tid}", (x1, max(30, y1 - 10)),
                            FONT, 1.0, COLOR_IGNORED, 2)
                continue

            op = self.operators.get(tid)
            if op is not None and op.status == ACTIVE:
                color, label = COLOR_ACTIVE, f"P{tid}  ACTIVE"
            elif op is not None and op.status == IDLE:
                color, label = COLOR_IDLE, f"P{tid}  IDLE"
            else:
                color, label = COLOR_PENDING, f"P{tid}  ..."

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5)

            (tw, th), _ = cv2.getTextSize(label, FONT, 1.4, 3)
            top = max(0, y1 - th - 24)
            cv2.rectangle(frame, (x1, top), (x1 + tw + 20, top + th + 24), color, -1)
            cv2.putText(frame, label, (x1 + 10, top + th + 8),
                        FONT, 1.4, (0, 0, 0), 3)

            if p["kxy"] is not None:
                dot = COLOR_ACTIVE if p["touching"] else (0, 0, 255)
                for k in WRISTS:
                    if p["kconf"][k] > self.wrist_conf:
                        x, y = p["kxy"][k]
                        cv2.circle(frame, (int(x), int(y)), 10, dot, -1)

        # Away list
        y = 60
        for tid, op in self.operators.items():
            if op.status == AWAY:
                cv2.putText(frame, f"P{tid} AWAY", (30, y),
                            FONT, 1.4, (60, 60, 255), 3)
                y += 50