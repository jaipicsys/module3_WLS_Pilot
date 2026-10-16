import os
import re
import time
from collections import deque
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

# Operator states
ACTIVE = "active_work"
IDLE = "idle"

# COCO keypoints: left/right elbow, left/right wrist
ARM_KEYPOINTS = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

FONT = cv2.FONT_HERSHEY_SIMPLEX

# Box colors (BGR) per model class name
OBJECT_COLORS = {
    "towel": (255, 160, 0),
    "closed_box": (0, 165, 255),
    "trolly_box": (255, 0, 200),
    "yellow_person": (0, 255, 255),
}

# Per-operator labels on the display video
STATE_LABELS = {ACTIVE: "ACTIVE", IDLE: "IDLE"}
STATE_COLORS = {
    ACTIVE: (0, 200, 0),     # green
    IDLE: (0, 165, 255),     # orange
}


def _cam_number(camera_id):
    """'cam1' -> 1 (db column cam_id is INTEGER)."""
    digits = re.sub(r"\D", "", str(camera_id))
    return int(digits) if digits else None


class PersonMotion:
    """Arm movement of one operator, in body-heights per second."""

    def __init__(self, window_seconds):
        self.window = window_seconds
        self.prev = None            # (t, xy, conf)
        self.samples = deque()      # (t, speed)

    def update(self, t, xy, conf, height, kp_conf):
        if self.prev is not None:
            prev_t, prev_xy, prev_conf = self.prev
            dt = t - prev_t

            if dt > 1.0:
                # Out of view for a while: start fresh.
                self.samples.clear()
            elif dt > 0 and height > 0:
                visible = (conf > kp_conf) & (prev_conf > kp_conf)
                if visible.any():
                    disp = np.linalg.norm(
                        xy[visible] - prev_xy[visible], axis=1
                    ).mean()
                    self.samples.append((t, disp / height / dt))

        self.prev = (t, xy, conf)

        while self.samples and t - self.samples[0][0] > self.window:
            self.samples.popleft()

    def speed(self):
        """Mean arm speed over the window, or None if not enough data yet."""
        if len(self.samples) < 3:
            return None
        span = self.samples[-1][0] - self.samples[0][0]
        if span < self.window * 0.5:
            return None
        return float(np.mean([s for _, s in self.samples]))


class OperatorStatus:
    """Debounced ACTIVE/IDLE state and open DB row for ONE operator."""

    def __init__(self, now):
        self.status = None              # committed (debounced) state
        self.since = None               # when the committed state began
        self.candidate = None           # state waiting to pass the debounce
        self.candidate_since = None
        self.segment_id = None          # open operator_status row id
        self.last_inside = now          # last time seen inside the station


class FrameLogic:
    """
    Per-camera logic.

    model    -> detects Person / Towel / Closed_Box / Trolly_Box / Yellow_Person
                (ignored classes such as Inspection_Person are never tracked)
    ids      -> raw tracker ids are mapped to stable operator ids (OP1..OPn)
    pose     -> arm movement of each operator inside the station ROI
    Output   -> one operator_status row per operator (ACTIVE / IDLE segments)
    """

    def __init__(self, camera_id):
        self.camera_id = camera_id

        found = find_station_for_camera(camera_id)
        if found is None:
            raise ValueError(f"No station configured for camera '{camera_id}'")
        self.line_id, self.line, self.station_id, self.station = found

        self.roi_np = np.array(
            self.station["roi"], dtype=np.int32
        ).reshape(-1, 1, 2)

        cfg = CONFIG.get("operator_status", {})

        tracker = cfg.get("tracker", "bytetrack.yaml")
        local_tracker = os.path.join(BASE_DIR, tracker)
        self.tracker = local_tracker if os.path.exists(local_tracker) else tracker

        self.pose_conf = cfg.get("pose_conf", 0.5)
        self.kp_conf = cfg.get("keypoint_conf", 0.5)
        self.window = cfg.get("motion_window_seconds", 2.0)
        self.motion_threshold = cfg.get("motion_threshold", 0.12)
        self.debounce = cfg.get("debounce_seconds", 5)
        self.away_seconds = cfg.get("away_seconds", 30)
        self.max_operators = cfg.get("max_operators", 0)        # 0 = unlimited
        self.reid_seconds = cfg.get("reid_seconds", 20)
        self.reid_distance = cfg.get("reid_distance", 1.0)      # in body heights
        self.ignore_names = [n.lower() for n in cfg.get("ignore_classes", [])]
        self.draw = CONFIG.get("enable_display", False)

        # ---- device (GPU if available) ----
        device = CONFIG.get("device", "auto")
        if device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.half = self.device != "cpu"   # FP16 is faster on GPU

        if self.device == "cpu":
            print(f"[WARNING] {camera_id}: running on CPU (slow). "
                  f"CUDA available: {torch.cuda.is_available()}")
        else:
            print(f"[INFO] {camera_id}: running on {self.device} "
                  f"({torch.cuda.get_device_name(0)})")

        # ---- models ----
        op_cfg = CONFIG["operations"][self.station["operation"]]
        self.det_conf = op_cfg.get("conf_thresh", 0.6)            # objects
        self.person_conf = cfg.get("person_conf", self.det_conf)  # people
        self.track_conf = min(self.det_conf, self.person_conf)

        self.det_model = YOLO(resolve_model_path(op_cfg["model"]))
        self.pose_model = YOLO(resolve_model_path(CONFIG["pose_model"]))

        # Find class ids from the model's own class names
        self.names = self.det_model.names
        lower_names = {i: n.lower() for i, n in self.names.items()}

        person_ids = [i for i, n in lower_names.items() if n == "person"]
        if not person_ids:
            raise ValueError(f"'Person' class not found in model: {self.names}")
        self.person_class = person_ids[0]

        # Classes to ignore completely (e.g. Inspection_Person)
        unknown = [n for n in self.ignore_names if n not in lower_names.values()]
        if unknown:
            raise ValueError(
                f"ignore_classes {unknown} not found in model: {self.names}"
            )
        ignore_ids = {i for i, n in lower_names.items() if n in self.ignore_names}

        # Only these classes are given to the tracker
        self.track_classes = [i for i in self.names if i not in ignore_ids]
        print(f"[INFO] {camera_id}: tracking {[self.names[i] for i in self.track_classes]}, "
              f"ignoring {[self.names[i] for i in sorted(ignore_ids)]}")

        # ---- stable operator ids ----
        self.id_map = {}        # raw tracker id -> stable id
        self.slots = {}         # stable id -> {"pos": (x, y), "seen": time}
        self.next_sid = 1

        self.motions = {}       # stable id -> PersonMotion
        self.operators = {}     # stable id -> OperatorStatus

    # ---------------- main entry ----------------

    def process(self, frame):
        now = time.time()
        persons, objects = self._detect(frame, now)

        self._update_operators(persons, now)

        if self.draw:
            self._draw(frame, persons, objects)

        return frame

    # ---------------- detection + tracking ----------------

    @staticmethod
    def _anchor(box):
        x1, y1, x2, y2 = box
        return (float((x1 + x2) / 2), float(y2))  # bottom-center

    def _inside_roi(self, box):
        return cv2.pointPolygonTest(self.roi_np, self._anchor(box), False) >= 0

    def _detect(self, frame, now):
        """Model detects everything; pose runs only on operators inside the ROI."""
        result = self.det_model.track(
            frame,
            persist=True,
            tracker=self.tracker,
            conf=self.track_conf,
            classes=self.track_classes,     # ignored classes never reach the tracker
            device=self.device,
            half=self.half,
            verbose=False,
        )[0]

        persons = []
        objects = []

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

                if name.lower() in self.ignore_names:
                    continue  # safety net

                inside = self._inside_roi(box)

                if cls != self.person_class:
                    if conf >= self.det_conf:
                        objects.append({
                            "id": tid,
                            "name": name,
                            "conf": float(conf),
                            "box": box,
                            "inside": inside,
                        })
                    continue

                if tid is None or conf < self.person_conf:
                    continue  # not tracked yet / too weak

                persons.append({
                    "raw_id": tid,      # ByteTrack id (can change)
                    "id": None,         # stable operator id (set below)
                    "box": box,
                    "inside": inside,
                    "speed": None,
                    "kxy": None,
                    "kconf": None,
                })

        # Map raw tracker ids -> stable operator ids (inside the station only)
        self._assign_stable_ids([p for p in persons if p["inside"]], now)

        # Pose + arm motion per stable operator
        for p in persons:
            sid = p["id"]
            if sid is None:
                continue

            kxy, kconf = self._pose_on_crop(frame, p["box"])
            p["kxy"], p["kconf"] = kxy, kconf

            if kxy is not None:
                motion = self.motions.setdefault(sid, PersonMotion(self.window))
                motion.update(
                    now,
                    kxy[ARM_KEYPOINTS],
                    kconf[ARM_KEYPOINTS],
                    p["box"][3] - p["box"][1],
                    self.kp_conf,
                )
            if sid in self.motions:
                p["speed"] = self.motions[sid].speed()

        # forget operators not seen for a long time
        for sid in [s for s, d in self.slots.items() if now - d["seen"] > 300]:
            self.slots.pop(sid, None)
            self.motions.pop(sid, None)
            for raw in [r for r, s in self.id_map.items() if s == sid]:
                self.id_map.pop(raw, None)

        return persons, objects

    # ---------------- stable ids ----------------

    def _assign_stable_ids(self, inside_persons, now):
        """
        Give each person inside the station a stable id.

        1. A raw id we already know keeps its stable id.
        2. A new raw id takes over the nearest operator who was lost recently
           (within reid_seconds and reid_distance body heights).
        3. If max_operators is reached, a new raw id always takes over the
           nearest free operator, so no extra operators are ever created.
        """
        used = set()
        new = []

        for p in inside_persons:
            sid = self.id_map.get(p["raw_id"])
            if sid is not None and sid not in used:
                p["id"] = sid
                used.add(sid)
            else:
                self.id_map.pop(p["raw_id"], None)
                new.append(p)

        if new:
            at_cap = (
                self.max_operators > 0 and len(self.slots) >= self.max_operators
            )

            pairs = []
            for i, p in enumerate(new):
                ax, ay = self._anchor(p["box"])
                height = max(1.0, p["box"][3] - p["box"][1])
                for sid, slot in self.slots.items():
                    if sid in used:
                        continue
                    dist = np.hypot(ax - slot["pos"][0], ay - slot["pos"][1])
                    recent = now - slot["seen"] <= self.reid_seconds
                    close = dist <= self.reid_distance * height
                    if at_cap or (recent and close):
                        pairs.append((dist / height, i, sid))

            pairs.sort()
            assigned = set()
            for _, i, sid in pairs:
                if i in assigned or sid in used:
                    continue
                new[i]["id"] = sid
                self.id_map[new[i]["raw_id"]] = sid
                used.add(sid)
                assigned.add(i)

            # Anyone left becomes a new operator (unless the cap is reached)
            for i, p in enumerate(new):
                if i in assigned:
                    continue
                if self.max_operators > 0 and len(self.slots) >= self.max_operators:
                    continue
                sid = self.next_sid
                self.next_sid += 1
                self.slots[sid] = {"pos": self._anchor(p["box"]), "seen": now}
                p["id"] = sid
                self.id_map[p["raw_id"]] = sid
                used.add(sid)

        # Refresh position / last seen for everyone we matched
        for p in inside_persons:
            if p["id"] is not None:
                slot = self.slots.setdefault(
                    p["id"], {"pos": self._anchor(p["box"]), "seen": now}
                )
                slot["pos"] = self._anchor(p["box"])
                slot["seen"] = now

    def _pose_on_crop(self, frame, box):
        """Pose model on one person's box. Returns (xy, conf) in full-frame coords."""
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

    # ---------------- per-operator active / idle ----------------

    def _update_operators(self, persons, now):
        for p in persons:
            sid = p["id"]
            if sid is None:
                continue

            op = self.operators.get(sid)
            if op is not None:
                op.last_inside = now

            if p["speed"] is None:
                continue  # not enough motion history yet

            raw = ACTIVE if p["speed"] >= self.motion_threshold else IDLE

            if op is None:
                op = self.operators[sid] = OperatorStatus(now)

            self._update_person(sid, op, raw, now)

        # Operator left the station (or lost) -> close their row
        for sid in list(self.operators):
            op = self.operators[sid]
            if now - op.last_inside > self.away_seconds:
                self._close_person(sid, op, op.last_inside)
                del self.operators[sid]

    def _update_person(self, sid, op, raw, now):
        if op.status is None:
            self._commit_person(sid, op, raw, now)
            return

        if raw == op.status:
            op.candidate = None
            return

        if raw != op.candidate:
            op.candidate = raw
            op.candidate_since = now
            return

        if now - op.candidate_since >= self.debounce:
            # backdate to when the new state actually began
            self._commit_person(sid, op, raw, op.candidate_since)

    def _commit_person(self, sid, op, state, start_ts):
        print(f"[STATUS] {self.camera_id} OP{sid}: {op.status} -> {state}")

        try:
            if op.segment_id is not None:
                operator_db.close_segment(
                    op.segment_id,
                    self._iso(start_ts),
                    start_ts - op.since,
                )

            op.segment_id = operator_db.open_segment(
                self._build_row(state, datetime.fromtimestamp(start_ts), sid)
            )
        except Exception as e:
            print(f"[ERROR] operator_status write failed: {e}")

        op.status = state
        op.since = start_ts
        op.candidate = None

    def _close_person(self, sid, op, end_ts):
        if op.segment_id is None:
            return
        try:
            operator_db.close_segment(
                op.segment_id, self._iso(end_ts), end_ts - op.since
            )
            print(f"[STATUS] {self.camera_id} OP{sid}: left station")
        except Exception as e:
            print(f"[ERROR] operator_status close failed: {e}")

    @staticmethod
    def _iso(ts):
        return datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")

    def _build_row(self, state, start_dt, sid):
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
            "reasons": None,
            "operator_id": f"OP{sid}",
            "plant": CONFIG.get("plant"),
        }

    # ---------------- drawing (only when enable_display / recording) ----------------

    def _person_state(self, p):
        """Committed ACTIVE / IDLE for this operator, or None if not measured yet."""
        if p["id"] is None:
            return None
        op = self.operators.get(p["id"])
        return op.status if op else None

    def _draw(self, frame, persons, objects):
        cv2.polylines(frame, [self.roi_np], True, (0, 255, 255), 4)

        # Towel / boxes / other objects
        for o in objects:
            x1, y1, x2, y2 = map(int, o["box"])
            color = OBJECT_COLORS.get(o["name"].lower(), (200, 200, 0))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            cv2.putText(frame, f"{o['name']} {o['conf']:.2f}",
                        (x1, max(30, y1 - 10)), FONT, 1.0, color, 2)

        # Each operator: box + stable ID + ACTIVE / IDLE
        for p in persons:
            x1, y1, x2, y2 = map(int, p["box"])
            state = self._person_state(p)

            if p["id"] is None:
                color = (160, 160, 160)                      # outside the station
                label = f"T{p['raw_id']}"
            elif state is None:
                color = (200, 200, 200)                      # still measuring
                label = f"OP{p['id']}  ..."
            else:
                color = STATE_COLORS[state]
                speed = "" if p["speed"] is None else f"  {p['speed']:.2f}"
                label = f"OP{p['id']}  {STATE_LABELS[state]}{speed}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5)

            # Filled label bar above the box
            (tw, th), _ = cv2.getTextSize(label, FONT, 1.6, 4)
            top = max(0, y1 - th - 24)
            cv2.rectangle(frame, (x1, top), (x1 + tw + 20, top + th + 24), color, -1)
            cv2.putText(frame, label, (x1 + 10, top + th + 8),
                        FONT, 1.6, (0, 0, 0), 4)

            if p["kxy"] is not None:
                for k in ARM_KEYPOINTS:
                    if p["kconf"][k] > self.kp_conf:
                        x, y = p["kxy"][k]
                        cv2.circle(frame, (int(x), int(y)), 8, (0, 0, 255), -1)

        in_station = sum(1 for p in persons if p["id"] is not None)
        cv2.putText(frame, f"Operators in station: {in_station}",
                    (30, 60), FONT, 1.8, (255, 255, 255), 4)