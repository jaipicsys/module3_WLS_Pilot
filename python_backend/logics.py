import re
import time
from datetime import datetime

import cv2
import numpy as np
import torch
from ultralytics import YOLO

import operator_db
import unit_count_db
from box_counter import BoxCounter
from config_utils import (
    CONFIG,
    find_station_for_camera,
    get_shift_and_break,
    resolve_model_path,
)

ACTIVE = "active_work"
IDLE = "idle"
AWAY = "away"

REASON_AWAY = "Operator not in ROI"

# COCO keypoints: left wrist, right wrist
WRISTS = [9, 10]

FONT = cv2.FONT_HERSHEY_SIMPLEX

OBJECT_COLORS = {
    "towel": (255, 160, 0),
    "closed_box": (0, 165, 255),
    "box_with_towel": (0, 200, 255),
    "trolly_box": (255, 120, 0),
    "yellow_person": (0, 255, 255),
}

COLOR_ACTIVE = (0, 200, 0)
COLOR_IDLE = (0, 165, 255)
COLOR_AWAY = (60, 60, 255)
COLOR_SEAT = (0, 255, 255)
COLOR_PENDING = (200, 200, 200)
COLOR_DEBUG = (255, 255, 255)
COLOR_NO_POSE = (130, 130, 130)

LOGICS = {
    "wrist_on_towel": {
        "method": "_logic_wrist_on_towel",
        "needs_pose": True,
        "idle_reason": "No towel or pose not detected",
    },
    "box_with_towel_overlap": {
        "method": "_logic_box_with_towel_overlap",
        "needs_pose": False,
        "idle_reason": "No box with towel",
    },
    "always_active": {
        "method": "_logic_always_active",
        "needs_pose": False,
        "idle_reason": None,
    },
    "box_near": {
        "method": "_logic_box_near",
        "needs_pose": False,
        "idle_reason": "Waiting for box",
    },
}


def _cam_number(camera_id):
    digits = re.sub(r"\D", "", str(camera_id))
    return int(digits) if digits else None


def _poly(points):
    return np.array(points, dtype=np.int32).reshape(-1, 1, 2)


def _inside(poly, point):
    return cv2.pointPolygonTest(
        poly, (float(point[0]), float(point[1])), False
    ) >= 0


def _overlap_ratio(person_box, obj_box):
    """Share of obj_box that lies inside person_box (0..1)."""
    ix1 = max(person_box[0], obj_box[0])
    iy1 = max(person_box[1], obj_box[1])
    ix2 = min(person_box[2], obj_box[2])
    iy2 = min(person_box[3], obj_box[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area = max(1.0, (obj_box[2] - obj_box[0]) * (obj_box[3] - obj_box[1]))
    return inter / area


def _boxes_touch(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


class OperatorState:
    def __init__(self):
        self.status = None
        self.since = None
        self.segment_id = None
        self.candidate = None
        self.candidate_since = None
        self.last_seen = None
        self.last_touch = None
        self.present_since = None


class FrameLogic:
    """
    1. Operators: one ROI each, own logic -> ACTIVE / IDLE / AWAY.
    2. Boxes: BoxCounter (line crossing while a trolley is in the zone).
    """

    def __init__(self, camera_id):
        self.camera_id = camera_id

        found = find_station_for_camera(camera_id)
        if found is None:
            raise ValueError(f"No station configured for camera '{camera_id}'")
        self.line_id, self.line, self.station_id, self.station = found

        cfg = CONFIG.get("operator_status", {})
        self.person_conf = cfg.get("person_conf", 0.3)
        self.pose_conf = cfg.get("pose_conf", 0.5)
        self.wrist_conf = cfg.get("wrist_conf", 0.3)
        self.pose_min_kp = cfg.get("pose_min_keypoints", 6)
        self.pose_kp_conf = cfg.get("pose_kp_conf", 0.4)
        self.towel_name = cfg.get("towel_class", "Towel").lower()
        self.towel_conf = cfg.get("towel_conf", 0.3)
        self.towel_margin = cfg.get("towel_margin", 0.05)
        self.bwt_name = cfg.get("box_with_towel_class", "box_with_towel").lower()
        self.bwt_conf = cfg.get("box_with_towel_conf", 0.3)
        self.overlap_min = cfg.get("box_overlap_min", 0.05)
        self.near_names = [n.lower() for n in
                           cfg.get("near_box_classes", ["Closed_Box", "box_with_towel"])]
        self.near_conf = cfg.get("near_box_conf", 0.3)
        self.near_margin = cfg.get("near_box_margin", 0.3)
        self.hold = cfg.get("active_hold_seconds", 3)
        self.debounce = cfg.get("debounce_seconds", 0)
        self.away_seconds = cfg.get("away_seconds", 5)
        self.debug_draw = cfg.get("debug_draw", False)
        self.ignore_names = [n.lower() for n in cfg.get("ignore_classes", [])]
        self.draw = CONFIG.get("enable_display", False)

        # ---- operators ----
        self.ops = {}
        for oid, o in self.station.get("operators", {}).items():
            if not o.get("enabled", True):
                continue
            if len(o.get("roi") or []) < 3:
                print(f"[WARNING] {camera_id}: {oid} has no ROI, skipped")
                continue
            logic = o.get("logic", "wrist_on_towel")
            if logic not in LOGICS:
                raise ValueError(f"{oid}: unknown logic '{logic}'. Available: {list(LOGICS)}")
            spec = LOGICS[logic]
            self.ops[oid] = {
                "roi": _poly(o["roi"]),
                "centre": np.array(o["roi"], dtype=float).mean(axis=0),
                "logic": getattr(self, spec["method"]),
                "logic_name": logic,
                "needs_pose": spec["needs_pose"],
                "idle_reason": spec["idle_reason"],
                "wrist_conf": o.get("wrist_conf", self.wrist_conf),
                "towel_margin": o.get("towel_margin", self.towel_margin),
                "overlap_min": o.get("box_overlap_min", self.overlap_min),
                "pose_min_kp": o.get("pose_min_keypoints", self.pose_min_kp),
                "near_margin": o.get("near_box_margin", self.near_margin),
                "hold": o.get("active_hold_seconds", self.hold),
            }
        if not self.ops:
            raise ValueError(f"Station {self.station_id}: no enabled operators")

        # ---- box counting ----
        bc = self.station.get("box_count") or {}
        zone = bc.get("zone") or []
        line = bc.get("line") or []
        if len(zone) < 3:
            raise ValueError(f"Station {self.station_id}: box_count.zone needs 3+ points")
        if len(line) != 3:
            raise ValueError(f"Station {self.station_id}: box_count.line needs 3 points")

        self.trolley_name = bc.get("trolley_class", "Trolly_Box").lower()
        self.box_names = [n.lower() for n in bc.get("box_classes", ["Closed_Box"])]
        self.trolley_conf = bc.get("trolley_conf", 0.4)
        self.box_conf = bc.get("box_conf", 0.4)

        self.counter = BoxCounter(
            zone=zone,
            line=tuple(tuple(p) for p in line),
            full_count=bc.get("boxes_per_trolley", 12),
            absent_s=bc.get("trolley_absent_s", 5),
            cooldown_s=bc.get("cooldown_s", 5),
        )
        self._last_sets = 0
        self._cin = {"trolleys": [], "boxes": []}

        # ---- device ----
        device = CONFIG.get("device", "auto")
        if device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.half = self.device != "cpu"
        print(f"[INFO] {camera_id}: running on {self.device}")

        # ---- models ----
        op_cfg = CONFIG["operations"][self.station["operation"]]
        self.det_conf = op_cfg.get("conf_thresh", 0.6)
        self.detect_conf = min(
            self.det_conf, self.person_conf, self.towel_conf,
            self.bwt_conf, self.near_conf, self.trolley_conf, self.box_conf,
        )

        self.det_model = YOLO(resolve_model_path(op_cfg["model"]))
        self.pose_model = YOLO(resolve_model_path(CONFIG["pose_model"]))

        self.names = self.det_model.names
        lower = {i: n.lower() for i, n in self.names.items()}

        person_ids = [i for i, n in lower.items() if n == "person"]
        if not person_ids:
            raise ValueError(f"'Person' class not found in model: {self.names}")
        self.person_class = person_ids[0]

        for what, names in (("Towel", [self.towel_name]),
                            ("box_with_towel", [self.bwt_name]),
                            ("trolley_class", [self.trolley_name]),
                            ("box_classes", self.box_names),
                            ("near_box_classes", self.near_names),
                            ("ignore_classes", self.ignore_names)):
            bad = [n for n in names if n not in lower.values()]
            if bad:
                raise ValueError(f"{what} {bad} not in model: {self.names}")

        ignore_ids = {i for i, n in lower.items() if n in self.ignore_names}
        self.detect_classes = [i for i in self.names if i not in ignore_ids]

        print(f"[INFO] {camera_id}: operators "
              f"{ {k: v['logic_name'] for k, v in self.ops.items()} }")

        self.state = {oid: OperatorState() for oid in self.ops}
        self.raw = []

    # ---------------- main entry ----------------

    def process(self, frame):
        now = time.time()
        persons, towels, bwts, near, objects, boxes = self._detect(frame)

        ctx = {"towels": towels, "bwts": bwts, "near": near}
        for p in persons:
            o = self.ops[p["op"]]
            o["logic"](p, ctx, o)

        self._update_operators(persons, now)
        self._count_boxes(now)

        if self.draw:
            self._draw(frame, persons, towels, bwts, near, objects, boxes, now)

        return frame

    def on_stream_gap(self):
        """Called by the camera worker when the stream drops."""
        self.counter.reset_tracks()

    # ---------------- detection ----------------

    def _detect(self, frame):
        result = self.det_model.predict(
            frame,
            conf=self.detect_conf,
            classes=self.detect_classes,
            device=self.device,
            half=self.half,
            verbose=False,
        )[0]

        people, towels, bwts, near, objects, boxes_out = [], [], [], [], [], []
        c_trolleys, c_boxes = [], []
        self.raw = []

        boxes = result.boxes
        if boxes is not None and len(boxes) > 0:
            xyxy = boxes.xyxy.cpu().numpy()
            classes = boxes.cls.int().cpu().tolist()
            confs = boxes.conf.cpu().numpy()

            for box, cls, conf in zip(xyxy, classes, confs):
                name = self.names[cls]
                lname = name.lower()
                self.raw.append((name, float(conf), box))
                tbox = tuple(float(v) for v in box)

                if cls == self.person_class:
                    if conf >= self.person_conf:
                        people.append({"box": box})
                    continue

                if lname == self.towel_name:
                    if conf >= self.towel_conf:
                        towels.append({"box": box, "conf": float(conf), "touched": False})
                    continue

                drawn = False

                if lname == self.trolley_name and conf >= self.trolley_conf:
                    c_trolleys.append(tbox)
                    boxes_out.append({"name": name, "conf": float(conf), "box": box})
                    drawn = True

                if lname in self.box_names and conf >= self.box_conf:
                    c_boxes.append(tbox)
                    boxes_out.append({"name": name, "conf": float(conf), "box": box})
                    drawn = True

                if lname == self.bwt_name and conf >= self.bwt_conf:
                    bwts.append({"box": box, "conf": float(conf), "touched": False})

                if lname in self.near_names and conf >= self.near_conf:
                    near.append({"name": name, "box": box, "conf": float(conf),
                                 "touched": False})

                if not drawn and lname != self.bwt_name and conf >= self.det_conf:
                    objects.append({"name": name, "conf": float(conf), "box": box})

        self._cin = {"trolleys": c_trolleys, "boxes": c_boxes}

        persons = self._assign_operators(people)

        for p in persons:
            if self.ops[p["op"]]["needs_pose"]:
                p["kxy"], p["kconf"] = self._pose_on_crop(frame, p["box"])

        return persons, towels, bwts, near, objects, boxes_out

    def _assign_operators(self, people):
        """A person is in an ROI if their centre or feet are inside it.
        One person per operator (nearest to the ROI centre)."""
        pairs = []
        for i, p in enumerate(people):
            x1, y1, x2, y2 = p["box"]
            centre = ((x1 + x2) / 2, (y1 + y2) / 2)
            feet = ((x1 + x2) / 2, y2)
            for oid, o in self.ops.items():
                if _inside(o["roi"], centre) or _inside(o["roi"], feet):
                    sx, sy = o["centre"]
                    pairs.append((np.hypot(centre[0] - sx, centre[1] - sy), i, oid))

        pairs.sort()
        used_p, used_o, out = set(), set(), []
        for _, i, oid in pairs:
            if i in used_p or oid in used_o:
                continue
            used_p.add(i)
            used_o.add(oid)
            out.append({
                "box": people[i]["box"], "op": oid, "working": False,
                "kxy": None, "kconf": None, "pose_ok": False,
            })
        return out

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
            crop, conf=self.pose_conf, device=self.device,
            half=self.half, verbose=False,
        )[0]

        if res.keypoints is None or res.boxes is None or len(res.boxes) == 0:
            return None, None

        ox, oy = (x1 + x2) / 2 - cx1, (y1 + y2) / 2 - cy1
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

    # ---------------- operator logics ----------------

    def _logic_wrist_on_towel(self, p, ctx, o):
        """Real pose AND a wrist on a towel -> working."""
        p["working"] = False
        p["pose_ok"] = False

        if p["kxy"] is None:
            return

        confident = int((p["kconf"] > self.pose_kp_conf).sum())
        if confident < o["pose_min_kp"]:
            return
        p["pose_ok"] = True

        margin = (p["box"][3] - p["box"][1]) * o["towel_margin"]

        for k in WRISTS:
            if p["kconf"][k] <= o["wrist_conf"]:
                continue
            wx, wy = p["kxy"][k]
            for t in ctx["towels"]:
                tx1, ty1, tx2, ty2 = t["box"]
                if (tx1 - margin <= wx <= tx2 + margin
                        and ty1 - margin <= wy <= ty2 + margin):
                    p["working"] = True
                    t["touched"] = True

    def _logic_box_with_towel_overlap(self, p, ctx, o):
        """A box_with_towel overlaps the person's box."""
        p["working"] = False
        for b in ctx["bwts"]:
            if _overlap_ratio(p["box"], b["box"]) >= o["overlap_min"]:
                p["working"] = True
                b["touched"] = True

    def _logic_always_active(self, p, ctx, o):
        """In the ROI means ACTIVE."""
        p["working"] = True

    def _logic_box_near(self, p, ctx, o):
        """A box is near him -> working. No box near -> waiting (IDLE)."""
        p["working"] = False

        x1, y1, x2, y2 = p["box"]
        m = (y2 - y1) * o["near_margin"]
        zone = (x1 - m, y1 - m, x2 + m, y2 + m)

        for b in ctx["near"]:
            if _boxes_touch(zone, b["box"]):
                p["working"] = True
                b["touched"] = True

    # ---------------- box counting ----------------

    def _count_boxes(self, now):
        n = self.counter.update(now, self._cin["trolleys"], self._cin["boxes"])

        if self.counter.sets > self._last_sets:
            print(f"[SET] {self.camera_id}: trolley complete, "
                  f"sets {self.counter.sets}")
            self._last_sets = self.counter.sets

        if n <= 0:
            return

        now_dt = datetime.now()
        shift, _ = get_shift_and_break(self.line, now_dt)
        info = {
            "line_id": self.line_id,
            "product_name": self.line.get("product_name"),
            "shift_id": shift["shift_id"] if shift else None,
            "shift_timings": shift["timings"] if shift else None,
            "operation": self.station.get("operation"),
            "station_name": self.station.get("station_name"),
            "cam_id": _cam_number(self.camera_id),
            "plant": CONFIG.get("plant"),
        }
        try:
            unit_count_db.add_count(info, n, now_dt)
            print(f"[COUNT] {self.camera_id}: +{n} box(es), "
                  f"on trolley {self.counter.on_trolley}/{self.counter.full_count}")
        except Exception as e:
            print(f"[ERROR] unit_count write failed: {e}")

    # ---------------- active / idle / away ----------------

    def _update_operators(self, persons, now):
        by_op = {p["op"]: p for p in persons}

        for oid, o in self.ops.items():
            st = self.state[oid]
            p = by_op.get(oid)

            if p is not None:
                if st.present_since is None:
                    st.present_since = now

                st.last_seen = now
                if p["working"]:
                    st.last_touch = now

                active = st.last_touch is not None and now - st.last_touch <= o["hold"]
                raw = ACTIVE if active else IDLE

                # Just appeared or just returned: wait the hold time before IDLE
                if (raw == IDLE
                        and st.status in (None, AWAY)
                        and now - st.present_since < o["hold"]):
                    continue

                self._update_status(oid, st, raw, now)
                continue

            st.present_since = None

            if (st.last_seen is not None
                    and now - st.last_seen >= self.away_seconds
                    and st.status is not None
                    and st.status != AWAY):
                self._commit(oid, st, AWAY, st.last_seen)

    def _update_status(self, oid, st, raw, now):
        if st.status is None:
            self._commit(oid, st, raw, now)
            return

        if raw == st.status:
            st.candidate = None
            return

        if raw != st.candidate:
            st.candidate = raw
            st.candidate_since = now
            return

        if now - st.candidate_since >= self.debounce:
            self._commit(oid, st, raw, st.candidate_since)

    def _commit(self, oid, st, state, start_ts):
        if st.since is not None:
            start_ts = max(start_ts, st.since)
        print(f"[STATUS] {self.camera_id} {oid}: {st.status} -> {state}")

        reason = (REASON_AWAY if state == AWAY
                  else self.ops[oid]["idle_reason"] if state == IDLE else None)
        try:
            if st.segment_id is not None:
                operator_db.close_segment(
                    st.segment_id, self._iso(start_ts), start_ts - st.since
                )
            st.segment_id = operator_db.open_segment(
                self._build_row(state, reason, datetime.fromtimestamp(start_ts), oid)
            )
        except Exception as e:
            print(f"[ERROR] operator_status write failed: {e}")

        st.status = state
        st.since = start_ts
        st.candidate = None

    @staticmethod
    def _iso(ts):
        return datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")

    def _build_row(self, state, reason, start_dt, oid):
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
            "operator_id": oid,
            "plant": CONFIG.get("plant"),
        }

    # ---------------- drawing ----------------

    def _draw(self, frame, persons, towels, bwts, near, objects, boxes, now):
        self.counter.draw(frame, now)

        if self.debug_draw:
            for name, conf, box in self.raw:
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_DEBUG, 1)
                cv2.putText(frame, f"{name} {conf:.2f}",
                            (x1, min(frame.shape[0] - 5, y2 + 22)),
                            FONT, 0.7, COLOR_DEBUG, 2)

        occupied = {p["op"] for p in persons}
        for oid, o in self.ops.items():
            cv2.polylines(frame, [o["roi"]], True, COLOR_SEAT, 3)
            cx, cy = o["centre"]
            st = self.state[oid]
            if oid in occupied:
                tag, color = oid, COLOR_SEAT
            elif st.status == AWAY:
                tag, color = f"{oid} AWAY", COLOR_AWAY
            else:
                tag, color = f"{oid} (empty)", COLOR_SEAT
            cv2.putText(frame, tag, (int(cx) - 50, int(cy)), FONT, 1.0, color, 2)

        for ob in objects:
            x1, y1, x2, y2 = map(int, ob["box"])
            color = OBJECT_COLORS.get(ob["name"].lower(), (200, 200, 0))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        for b in boxes:
            x1, y1, x2, y2 = map(int, b["box"])
            color = OBJECT_COLORS.get(b["name"].lower(), (0, 165, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{b['name']} {b['conf']:.2f}",
                        (x1, max(30, y1 - 10)), FONT, 0.8, color, 2)

        for b in bwts:
            x1, y1, x2, y2 = map(int, b["box"])
            color = COLOR_ACTIVE if b["touched"] else OBJECT_COLORS["box_with_towel"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5 if b["touched"] else 2)
            cv2.putText(frame, f"box_with_towel {b['conf']:.2f}",
                        (x1, max(30, y1 - 10)), FONT, 0.9, color, 2)

        for b in near:
            if b["touched"]:
                x1, y1, x2, y2 = map(int, b["box"])
                cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_ACTIVE, 5)

        for t in towels:
            x1, y1, x2, y2 = map(int, t["box"])
            color = COLOR_ACTIVE if t["touched"] else OBJECT_COLORS["towel"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5 if t["touched"] else 2)

        for p in persons:
            x1, y1, x2, y2 = map(int, p["box"])
            oid = p["op"]
            st = self.state[oid]

            if st.status == ACTIVE:
                color, label = COLOR_ACTIVE, f"{oid}  ACTIVE"
            elif st.status == IDLE:
                color, label = COLOR_IDLE, f"{oid}  IDLE"
            else:
                color, label = COLOR_PENDING, f"{oid}  ..."

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5)
            (tw, th), _ = cv2.getTextSize(label, FONT, 1.4, 3)
            top = max(0, y1 - th - 24)
            cv2.rectangle(frame, (x1, top), (x1 + tw + 20, top + th + 24), color, -1)
            cv2.putText(frame, label, (x1 + 10, top + th + 8),
                        FONT, 1.4, (0, 0, 0), 3)

            if p["kxy"] is not None:
                dot = COLOR_NO_POSE if not p["pose_ok"] else (
                    COLOR_ACTIVE if p["working"] else (0, 0, 255))
                wc = self.ops[oid]["wrist_conf"]
                for k in WRISTS:
                    if p["kconf"][k] > wc:
                        x, y = p["kxy"][k]
                        cv2.circle(frame, (int(x), int(y)), 10, dot, -1)