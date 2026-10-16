import re
import time
from datetime import datetime

import cv2
import numpy as np
import torch
from ultralytics import YOLO

import operator_db
from config_utils import (
    CONFIG,
    find_station_for_camera,
    get_shift_and_break,
    resolve_model_path,
)

# Operator states
ACTIVE = "active_work"
IDLE = "idle"

REASON_NO_TOWEL_TOUCH = "Wrist not on towel"

# COCO keypoints: left wrist, right wrist
WRISTS = [9, 10]

FONT = cv2.FONT_HERSHEY_SIMPLEX

OBJECT_COLORS = {
    "towel": (255, 160, 0),
    "closed_box": (0, 165, 255),
    "trolly_box": (255, 0, 200),
    "yellow_person": (0, 255, 255),
}

COLOR_ACTIVE = (0, 200, 0)       # green
COLOR_IDLE = (0, 165, 255)       # orange
COLOR_SEAT = (0, 255, 255)       # yellow
COLOR_STATION = (255, 255, 0)    # cyan
COLOR_UNASSIGNED = (160, 160, 160)


def _cam_number(camera_id):
    """'cam1' -> 1 (db column cam_id is INTEGER)."""
    digits = re.sub(r"\D", "", str(camera_id))
    return int(digits) if digits else None


def _poly(points):
    return np.array(points, dtype=np.int32).reshape(-1, 1, 2)


def _inside(poly, point):
    return cv2.pointPolygonTest(
        poly, (float(point[0]), float(point[1])), False
    ) >= 0


class OperatorStatus:
    """Debounced (state, reason) and open DB row for ONE seat / operator."""

    def __init__(self, now):
        self.key = None                 # committed (state, reason)
        self.since = None
        self.candidate = None
        self.candidate_since = None
        self.segment_id = None
        self.first_seen = now           # when this person appeared in the seat
        self.last_inside = now          # last time someone was in the seat
        self.last_touch = None          # last time a wrist was on a towel

    @property
    def status(self):
        return self.key[0] if self.key else None


class FrameLogic:
    """
    Station ROI  = the whole work area (people outside it are ignored).
    Seats        = OP1..OP4 ROIs inside the station.
    ACTIVE       = a wrist is on a towel.
    IDLE         = no wrist on a towel for idle_after_seconds.
    """

    def __init__(self, camera_id):
        self.camera_id = camera_id

        found = find_station_for_camera(camera_id)
        if found is None:
            raise ValueError(f"No station configured for camera '{camera_id}'")
        self.line_id, self.line, self.station_id, self.station = found

        # ---- station ROI ----
        if not self.station.get("roi"):
            raise ValueError(f"Station {self.station_id} has no 'roi' in config.json")
        self.station_roi = _poly(self.station["roi"])

        # ---- seats ----
        seats_cfg = self.station.get("seats", {})
        if not seats_cfg:
            raise ValueError(f"Station {self.station_id} has no 'seats' in config.json")

        self.seats = {}
        for seat_id, s in seats_cfg.items():
            self.seats[seat_id] = {
                "roi": _poly(s["roi"]),
                "centre": np.array(s["roi"], dtype=float).mean(axis=0),
            }

        # ---- settings ----
        cfg = CONFIG.get("operator_status", {})
        self.person_conf = cfg.get("person_conf", 0.3)
        self.pose_conf = cfg.get("pose_conf", 0.5)
        self.wrist_conf = cfg.get("wrist_conf", 0.3)
        self.towel_name = cfg.get("towel_class", "Towel").lower()
        self.towel_conf = cfg.get("towel_conf", 0.3)
        self.towel_margin = cfg.get("towel_margin", 0.05)
        self.idle_after = cfg.get("idle_after_seconds", 3)
        self.debounce = cfg.get("debounce_seconds", 1)
        self.away_seconds = cfg.get("away_seconds", 30)
        self.ignore_names = [n.lower() for n in cfg.get("ignore_classes", [])]
        self.draw = CONFIG.get("enable_display", False)

        # ---- device ----
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

        # ---- models ----
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

        print(f"[INFO] {camera_id}: seats {list(self.seats)}, "
              f"ignoring {[self.names[i] for i in sorted(ignore_ids)]}")

        self.operators = {}     # seat id -> OperatorStatus

    # ---------------- main entry ----------------

    def process(self, frame):
        now = time.time()
        persons, towels, objects = self._detect(frame)

        self._check_wrists(persons, towels, now)
        self._update_operators(persons, now)

        if self.draw:
            self._draw(frame, persons, towels, objects)

        return frame

    # ---------------- detection ----------------

    @staticmethod
    def _anchor(box):
        x1, y1, x2, y2 = box
        return (float((x1 + x2) / 2), float(y2))  # bottom-centre

    def _detect(self, frame):
        result = self.det_model.predict(
            frame,
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

            for box, cls, conf in zip(xyxy, classes, confs):
                name = self.names[cls]

                if cls == self.person_class:
                    if conf < self.person_conf:
                        continue
                    # Station ROI: ignore people outside the work area
                    if not _inside(self.station_roi, self._anchor(box)):
                        continue
                    persons.append({
                        "box": box, "seat": None,
                        "kxy": None, "kconf": None, "touching": False,
                    })
                elif name.lower() == self.towel_name:
                    if conf >= self.towel_conf:
                        towels.append({
                            "box": box, "conf": float(conf), "touched": False,
                        })
                elif conf >= self.det_conf:
                    objects.append({"name": name, "conf": float(conf), "box": box})

        self._assign_seats(persons)

        # Pose only for people sitting in one of the seats
        for p in persons:
            if p["seat"] is not None:
                p["kxy"], p["kconf"] = self._pose_on_crop(frame, p["box"])

        return persons, towels, objects

    def _assign_seats(self, persons):
        """A seat gets the person whose box centre is inside it (nearest wins)."""
        pairs = []
        for i, p in enumerate(persons):
            x1, y1, x2, y2 = p["box"]
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            for sid, seat in self.seats.items():
                if _inside(seat["roi"], (cx, cy)):
                    sx, sy = seat["centre"]
                    pairs.append((np.hypot(cx - sx, cy - sy), i, sid))

        pairs.sort()
        used_p, used_s = set(), set()
        for _, i, sid in pairs:
            if i in used_p or sid in used_s:
                continue
            persons[i]["seat"] = sid
            used_p.add(i)
            used_s.add(sid)

    def _pose_on_crop(self, frame, box):
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

        best = int(res.boxes.conf.argmax())
        xy = res.keypoints.xy[best].cpu().numpy() + np.array([cx1, cy1])
        conf = (
            res.keypoints.conf[best].cpu().numpy()
            if res.keypoints.conf is not None
            else np.ones(len(xy))
        )
        return xy, conf

    # ---------------- wrist on towel ----------------

    def _check_wrists(self, persons, towels, now):
        for p in persons:
            sid = p["seat"]
            if sid is None or p["kxy"] is None:
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

            if p["touching"]:
                op = self.operators.get(sid)
                if op is None:
                    op = self.operators[sid] = OperatorStatus(now)
                op.last_touch = now

    # ---------------- per-operator active / idle ----------------

    def _decide(self, op, now):
        """(state, reason), or None while we cannot decide yet."""
        if op.last_touch is not None and now - op.last_touch <= self.idle_after:
            return ACTIVE, None
        ref = op.last_touch if op.last_touch is not None else op.first_seen
        if now - ref >= self.idle_after:
            return IDLE, REASON_NO_TOWEL_TOUCH
        return None

    def _update_operators(self, persons, now):
        for p in persons:
            sid = p["seat"]
            if sid is None:
                continue

            op = self.operators.get(sid)
            if op is None:
                op = self.operators[sid] = OperatorStatus(now)
            op.last_inside = now

            key = self._decide(op, now)
            if key is None:
                continue

            self._update_person(sid, op, key, now)

        # Seat empty for too long -> close the open row
        for sid in list(self.operators):
            op = self.operators[sid]
            if now - op.last_inside > self.away_seconds:
                self._close_person(sid, op, op.last_inside)
                del self.operators[sid]

    def _update_person(self, sid, op, key, now):
        if op.key is None:
            self._commit_person(sid, op, key, now)
            return

        if key == op.key:
            op.candidate = None
            return

        if key != op.candidate:
            op.candidate = key
            op.candidate_since = now
            return

        if now - op.candidate_since >= self.debounce:
            self._commit_person(sid, op, key, op.candidate_since)

    def _commit_person(self, sid, op, key, start_ts):
        state, reason = key
        print(f"[STATUS] {self.camera_id} {sid}: {op.key} -> {key}")

        try:
            if op.segment_id is not None:
                operator_db.close_segment(
                    op.segment_id,
                    self._iso(start_ts),
                    start_ts - op.since,
                )

            op.segment_id = operator_db.open_segment(
                self._build_row(state, reason, datetime.fromtimestamp(start_ts), sid)
            )
        except Exception as e:
            print(f"[ERROR] operator_status write failed: {e}")

        op.key = key
        op.since = start_ts
        op.candidate = None

    def _close_person(self, sid, op, end_ts):
        if op.segment_id is None:
            return
        try:
            operator_db.close_segment(
                op.segment_id, self._iso(end_ts), end_ts - op.since
            )
            print(f"[STATUS] {self.camera_id} {sid}: left seat")
        except Exception as e:
            print(f"[ERROR] operator_status close failed: {e}")

    @staticmethod
    def _iso(ts):
        return datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")

    def _build_row(self, state, reason, start_dt, sid):
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
            "operator_id": sid,
            "plant": CONFIG.get("plant"),
        }

    # ---------------- drawing (only when enable_display / recording) ----------------

    def _draw(self, frame, persons, towels, objects):
        # Station ROI (outer boundary)
        cv2.polylines(frame, [self.station_roi], True, COLOR_STATION, 4)

        # Seat ROIs
        occupied = {p["seat"] for p in persons if p["seat"] is not None}
        for sid, seat in self.seats.items():
            cv2.polylines(frame, [seat["roi"]], True, COLOR_SEAT, 3)
            cx, cy = seat["centre"]
            tag = sid if sid in occupied else f"{sid} (empty)"
            cv2.putText(frame, tag, (int(cx) - 40, int(cy)),
                        FONT, 1.0, COLOR_SEAT, 2)

        # Other objects (boxes, trolly, yellow person)
        for o in objects:
            x1, y1, x2, y2 = map(int, o["box"])
            color = OBJECT_COLORS.get(o["name"].lower(), (200, 200, 0))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Towels: thick green when a wrist is on them
        for t in towels:
            x1, y1, x2, y2 = map(int, t["box"])
            color = COLOR_ACTIVE if t["touched"] else OBJECT_COLORS["towel"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5 if t["touched"] else 2)

        # People inside the station
        for p in persons:
            sid = p["seat"]
            x1, y1, x2, y2 = map(int, p["box"])

            if sid is None:
                # In the station, but not in OP1..OP4 (future operators)
                cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_UNASSIGNED, 3)
                cv2.putText(frame, "unassigned", (x1, max(30, y1 - 10)),
                            FONT, 1.0, COLOR_UNASSIGNED, 2)
                continue

            op = self.operators.get(sid)

            if op is None or op.key is None:
                color, label = (200, 200, 200), f"{sid}  ..."
            elif op.status == ACTIVE:
                color, label = COLOR_ACTIVE, f"{sid}  ACTIVE"
            else:
                color, label = COLOR_IDLE, f"{sid}  IDLE"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5)

            (tw, th), _ = cv2.getTextSize(label, FONT, 1.4, 3)
            top = max(0, y1 - th - 24)
            cv2.rectangle(frame, (x1, top), (x1 + tw + 20, top + th + 24), color, -1)
            cv2.putText(frame, label, (x1 + 10, top + th + 8),
                        FONT, 1.4, (0, 0, 0), 3)

            # Wrist dots: green if on a towel, red if not
            if p["kxy"] is not None:
                dot = COLOR_ACTIVE if p["touching"] else (0, 0, 255)
                for k in WRISTS:
                    if p["kconf"][k] > self.wrist_conf:
                        x, y = p["kxy"][k]
                        cv2.circle(frame, (int(x), int(y)), 10, dot, -1)