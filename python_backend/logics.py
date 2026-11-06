import re
import time
from datetime import datetime

import cv2
import numpy as np
import torch
from ultralytics import YOLO

import operator_db
import unit_count_db
from box_counter import PickCounter
from config_utils import (
    CONFIG,
    find_station_for_camera,
    get_shift_and_break,
    resolve_model_path,
)
from person_tracking import PersonTracker

ACTIVE = "active_work"
IDLE = "idle"
AWAY = "away"

REASON_AWAY = "Away"

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
COLOR_BOUND_ROI = (150, 150, 150)
COLOR_PENDING = (200, 200, 200)
COLOR_DEBUG = (255, 255, 255)
COLOR_NO_POSE = (130, 130, 130)
COLOR_YELLOW = (0, 255, 255)
COLOR_TRACK = (170, 170, 170)

_UNSET = object()

LOGICS = {
    "wrist_on_towel": {
        "method": "_logic_wrist_on_towel",
        "needs_pose": True,
        "idle_reason": "Waiting for materials",
    },
    "wrist_on_towel_or_box": {
        "method": "_logic_wrist_on_towel_or_box",
        "needs_pose": True,
        "idle_reason": "Waiting for materials",
    },
    "box_with_towel_overlap": {
        "method": "_logic_box_with_towel_overlap",
        "needs_pose": False,
        "idle_reason": "Others",
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


def _iou(a, b):
    """Intersection over union of two xyxy boxes."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / max(1e-9, ua)


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


class OperatorBinding:
    """Which P-ID uses this operator's logic. Decided once, from the ROI."""

    def __init__(self):
        self.gid = None          # P-ID that uses this operator's logic (None = not decided)
        self.cand = None         # P-ID being timed inside the ROI
        self.cand_since = None
        self.cand_last = None


class FrameLogic:
    """
    1. Operators = tracked people (P-IDs) -> ACTIVE / IDLE / AWAY.
       The operator ROIs are used ONLY at the start: the P-ID that settles in
       OP1's ROI (same ID for bind_seconds) gets OP1's logic, for the rest of
       the shift, wherever it moves. operator_status.operator_id = the P-ID
       ("P2"), not the operator name.
       A P-ID is only a binding candidate once it is "stable" (seen long enough
       / gallery learnt) and not overlapping another person.
       If the P-ID is not seen (ID switch, occlusion), its status is held for
       id_grace_seconds (30 s). Back within that time -> continues. Not back
       -> AWAY from the moment it was last seen.
    2. Units: the yellow person overlaps a closed box -> +1 (no pose).
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
        self.wobj_names = [n.lower() for n in
                           cfg.get("wrist_box_classes", ["box_with_towel", "Closed_Box"])]
        self.wobj_conf = cfg.get("wrist_box_conf", 0.3)
        self.hold = cfg.get("active_hold_seconds", 3)
        self.debounce = cfg.get("debounce_seconds", 0)
        self.away_seconds = cfg.get("away_seconds", 5)
        self.debug_draw = cfg.get("debug_draw", False)
        self.ignore_names = [n.lower() for n in cfg.get("ignore_classes", [])]
        self.draw = CONFIG.get("enable_display", False)

        # ---- ID binding ----
        tcfg = CONFIG.get("tracking", {})
        self.bind_seconds = tcfg.get("bind_seconds", 5)
        self.bind_gap = tcfg.get("bind_gap_seconds", 2)
        self.bind_min_seen = tcfg.get("bind_min_seen_seconds", 20)
        self.bind_need_frozen = tcfg.get("bind_require_frozen", False)
        self.id_grace = max(tcfg.get("id_grace_seconds", 30), self.away_seconds)
        self.reset_on_shift = tcfg.get("reset_on_shift_change", True)

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

        # ---- unit counting (yellow person, no pose) ----
        bc = self.station.get("box_count") or {}
        self.yellow_name = bc.get("person_class", "Yellow_Person").lower()
        self.yellow_conf = bc.get("person_conf", 0.4)
        self.box_names = [n.lower() for n in bc.get("box_classes", ["Closed_Box"])]
        self.box_conf = bc.get("box_conf", 0.4)
        self.pick_overlap_min = bc.get("overlap_min", 0.1)

        self.counter = PickCounter(
            overlap_frames=bc.get("overlap_frames", 5),
            release_s=bc.get("release_s", 2),
        )
        self._cin = {"yellow": [], "boxes": []}
        self._pick = None

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
            self.det_conf, self.towel_conf,
            self.bwt_conf, self.near_conf, self.yellow_conf, self.box_conf,
            self.wobj_conf,
        )

        det_weights = resolve_model_path(op_cfg["model"])
        self.det_model = YOLO(det_weights)
        self.pose_model = YOLO(resolve_model_path(CONFIG["pose_model"]))

        self.names = self.det_model.names
        lower = {i: n.lower() for i, n in self.names.items()}

        person_ids = [i for i, n in lower.items() if n == "person"]
        if not person_ids:
            raise ValueError(f"'Person' class not found in model: {self.names}")
        self.person_class = person_ids[0]

        for what, names in (("Towel", [self.towel_name]),
                            ("box_with_towel", [self.bwt_name]),
                            ("box_count person_class", [self.yellow_name]),
                            ("box_count box_classes", self.box_names),
                            ("near_box_classes", self.near_names),
                            ("wrist_box_classes", self.wobj_names),
                            ("ignore_classes", self.ignore_names)):
            bad = [n for n in names if n not in lower.values()]
            if bad:
                raise ValueError(f"{what} {bad} not in model: {self.names}")

        if self.yellow_name in self.ignore_names:
            raise ValueError("Yellow_Person must not be in ignore_classes")

        # People now come from the tracker, so the detector skips its person class.
        ignore_ids = {i for i, n in lower.items() if n in self.ignore_names}
        ignore_ids.add(self.person_class)
        self.detect_classes = [i for i in self.names if i not in ignore_ids]

        # ---- person tracking (stable P-IDs) ----
        self.tracker = PersonTracker(
            camera_id, self.device, self.half,
            fallback_weights=det_weights, fallback_class=self.person_class,
            roi=self.station.get("roi"),
        )
        self.station_roi = self.tracker.roi
        self.tracks = []
        self.bindings = {oid: OperatorBinding() for oid in self.ops}
        self._shift_id = _UNSET
        self._shift_checked = 0.0

        print(f"[INFO] {camera_id}: operators "
              f"{ {k: v['logic_name'] for k, v in self.ops.items()} }, "
              f"bind after {self.bind_seconds}s in ROI, "
              f"counting {self.box_names} touched by {self.yellow_name}")

        # Keyed by P-ID label ("P2"). camera_worker may replace this dict on a
        # stream gap; entries are created on demand, so that is fine.
        self.state = {}
        self.raw = []

    # ---------------- main entry ----------------

    def process(self, frame):
        now = time.time()
        self._check_shift(now)

        self.tracks = self.tracker.latest()  # tracker runs in its own process (camera_worker starts it)
        self._update_bindings(now)

        persons, towels, bwts, near, wobjs, objects, boxes = self._detect(frame)

        ctx = {"towels": towels, "bwts": bwts, "near": near, "wobjs": wobjs}
        for p in persons:
            o = self.ops[p["op"]]
            o["logic"](p, ctx, o)

        self._update_operators(persons, now)
        self._count_units(now)

        if self.draw:
            self._draw(frame, persons, towels, bwts, near, wobjs, objects, boxes, now)

        return frame

    def on_stream_gap(self):
        """Called by the camera worker when the stream drops.
        P-IDs and bindings are kept: the same people come back after a reconnect."""
        self.counter.reset()

    def reset_identities(self):
        """Forget all P-IDs and bindings (ROIs decide again). Open status rows
        are closed first, because the same P-ID may be a different person next."""
        now = time.time()
        for key, st in self.state.items():
            if st.segment_id is not None and st.since is not None:
                try:
                    operator_db.close_segment(st.segment_id, self._iso(now), now - st.since)
                except Exception as e:
                    print(f"[ERROR] closing {key} failed: {e}")
        self.state = {}
        self.tracker.reset()
        self.bindings = {oid: OperatorBinding() for oid in self.ops}
        print(f"[BIND] {self.camera_id}: all bindings cleared, ROIs decide again")

    def _check_shift(self, now):
        """New shift = new people: the closed set of P-IDs starts again."""
        if not self.reset_on_shift or now - self._shift_checked < 5:
            return
        self._shift_checked = now
        shift, _ = get_shift_and_break(self.line, datetime.now())
        sid = shift["shift_id"] if shift else None
        if self._shift_id is _UNSET:
            self._shift_id = sid
            return
        if sid != self._shift_id:
            print(f"[BIND] {self.camera_id}: shift {self._shift_id} -> {sid}")
            self._shift_id = sid
            self.reset_identities()

    # ---------------- ID <-> operator binding ----------------

    def _roi_dist(self, o, box):
        """Distance from the ROI centre if the box centre or feet are inside, else None."""
        x1, y1, x2, y2 = box
        centre = ((x1 + x2) / 2, (y1 + y2) / 2)
        feet = ((x1 + x2) / 2, y2)
        if _inside(o["roi"], centre) or _inside(o["roi"], feet):
            sx, sy = o["centre"]
            return float(np.hypot(centre[0] - sx, centre[1] - sy))
        return None

    def _update_bindings(self, now):
        """
        Only for operators that have no P-ID yet. The P-ID in the operator's ROI
        (nearest the centre) is timed; the same ID for bind_seconds -> that P-ID
        uses this operator's logic from now on. A different ID restarts the timer;
        a dropout up to bind_gap_seconds does not. Once bound, never changed
        (until a shift reset).

        A P-ID is only a candidate when it is stable (linked to a live track and
        seen for bind_min_seen_seconds, or its gallery is frozen) and its box does
        not overlap another person's box.
        """
        open_ops = [oid for oid, b in self.bindings.items() if b.gid is None]
        if not open_ops:
            return

        def ambiguous(t):
            return any(u is not t and _iou(t["box"], u["box"]) > 0.15
                       for u in self.tracks)

        visible = {
            t["gid"]: t for t in self.tracks
            if t["gid"] > 0
            and self.tracker.is_stable(t["gid"], self.bind_min_seen, self.bind_need_frozen)
            and not ambiguous(t)
        }
        taken = {b.gid for b in self.bindings.values() if b.gid is not None}

        pairs = []
        for oid in open_ops:
            for gid, t in visible.items():
                if gid in taken:
                    continue
                d = self._roi_dist(self.ops[oid], t["box"])
                if d is not None:
                    pairs.append((d, gid, oid))
        pairs.sort()

        chosen, used = {}, set()
        for _, gid, oid in pairs:
            if oid in chosen or gid in used:
                continue
            chosen[oid] = gid
            used.add(gid)

        for oid in open_ops:
            b = self.bindings[oid]
            cand = chosen.get(oid)

            if cand is None:
                if b.cand is not None and now - b.cand_last > self.bind_gap:
                    b.cand = None
                continue

            if cand != b.cand:
                b.cand, b.cand_since, b.cand_last = cand, now, now  # ID changed: restart
                continue

            b.cand_last = now
            if now - b.cand_since >= self.bind_seconds:
                b.gid, b.cand = cand, None
                taken.add(cand)
                print(f"[BIND] {self.camera_id}: P{cand} uses {oid} logic "
                      f"({self.ops[oid]['logic_name']})")

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

        towels, bwts, near, wobjs = [], [], [], []
        objects, boxes_out = [], []
        yellow, c_boxes = [], []
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

                if cls == self.person_class:
                    continue  # people come from the tracker

                if lname == self.towel_name:
                    if conf >= self.towel_conf:
                        towels.append({"box": box, "conf": float(conf), "touched": False})
                    continue

                if lname == self.yellow_name:
                    if conf >= self.yellow_conf:
                        yellow.append({"box": box, "conf": float(conf)})
                    continue

                drawn = False

                if lname in self.box_names and conf >= self.box_conf:
                    c_boxes.append(box)
                    boxes_out.append({"name": name, "conf": float(conf), "box": box})
                    drawn = True

                if lname == self.bwt_name and conf >= self.bwt_conf:
                    bwts.append({"box": box, "conf": float(conf), "touched": False})

                if lname in self.near_names and conf >= self.near_conf:
                    near.append({"name": name, "box": box, "conf": float(conf),
                                 "touched": False})

                if lname in self.wobj_names and conf >= self.wobj_conf:
                    wobjs.append({"name": name, "box": box, "conf": float(conf),
                                  "touched": False})

                if not drawn and lname != self.bwt_name and conf >= self.det_conf:
                    objects.append({"name": name, "conf": float(conf), "box": box})

        self._cin = {"yellow": yellow, "boxes": c_boxes}

        persons = self._assign_operators()

        for p in persons:
            if self.ops[p["op"]]["needs_pose"]:
                p["kxy"], p["kconf"] = self._pose_on_crop(frame, p["box"])

        return persons, towels, bwts, near, wobjs, objects, boxes_out

    def _assign_operators(self):
        """Every bound P-ID that is visible, with the operator whose logic it uses."""
        by_gid = {t["gid"]: i for i, t in enumerate(self.tracks) if t["gid"] > 0}
        out = []
        for oid, b in self.bindings.items():
            if b.gid is None or b.gid not in by_gid:
                continue
            i = by_gid[b.gid]
            t = self.tracks[i]
            out.append({
                "box": t["box"], "op": oid, "gid": b.gid, "key": f"P{b.gid}",
                "track_idx": i, "working": False,
                "kxy": None, "kconf": None, "pose_ok": False,
            })
        return out

    def _pose_on_crop(self, frame, box):
        """Pose of ONE operator; with overlap, take the pose nearest to this box."""
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

    def _wrist_hits(self, p, o, targets):
        """Mark p working if a trusted wrist is inside any target box."""
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
            for t in targets:
                tx1, ty1, tx2, ty2 = t["box"]
                if (tx1 - margin <= wx <= tx2 + margin
                        and ty1 - margin <= wy <= ty2 + margin):
                    p["working"] = True
                    t["touched"] = True

    def _logic_wrist_on_towel(self, p, ctx, o):
        """Real pose AND a wrist on a towel -> working."""
        self._wrist_hits(p, o, ctx["towels"])

    def _logic_wrist_on_towel_or_box(self, p, ctx, o):
        """Real pose AND a wrist on a towel or on a box -> working."""
        self._wrist_hits(p, o, ctx["towels"] + ctx["wobjs"])

    def _logic_box_with_towel_overlap(self, p, ctx, o):
        """A box_with_towel overlaps the person's box."""
        p["working"] = False
        for b in ctx["bwts"]:
            if _overlap_ratio(p["box"], b["box"]) >= o["overlap_min"]:
                p["working"] = True
                b["touched"] = True

    def _logic_always_active(self, p, ctx, o):
        """Visible means ACTIVE."""
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

    # ---------------- unit counting ----------------

    def _count_units(self, now):
        pick = None
        ys = self._cin["yellow"]

        if ys:
            y = max(ys, key=lambda d: d["conf"])
            box = y["box"]
            overlap = max((_overlap_ratio(box, b) for b in self._cin["boxes"]),
                          default=0.0)
            pick = {"box": box, "overlap": overlap}

        self._pick = pick

        overlapping = bool(pick and pick["overlap"] >= self.pick_overlap_min)
        n = self.counter.update(now, overlapping)

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
            print(f"[COUNT] {self.camera_id}: +{n} unit, "
                  f"session total {self.counter.total}")
        except Exception as e:
            print(f"[ERROR] unit_count write failed: {e}")

    # ---------------- active / idle / away ----------------

    def _update_operators(self, persons, now):
        by_op = {p["op"]: p for p in persons}

        for oid, b in self.bindings.items():
            if b.gid is None:
                continue
            o = self.ops[oid]
            key = f"P{b.gid}"
            st = self.state.setdefault(key, OperatorState())
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

                self._update_status(oid, key, st, raw, now)
                continue

            st.present_since = None

            # Not seen: hold the status for id_grace seconds (ID may come back).
            # AWAY then starts at the last time the P-ID was seen.
            if (st.last_seen is not None
                    and now - st.last_seen >= self.id_grace
                    and st.status is not None
                    and st.status != AWAY):
                self._commit(oid, key, st, AWAY, st.last_seen)

    def _update_status(self, oid, key, st, raw, now):
        if st.status is None:
            self._commit(oid, key, st, raw, now)
            return

        if raw == st.status:
            st.candidate = None
            return

        if raw != st.candidate:
            st.candidate = raw
            st.candidate_since = now
            return

        if now - st.candidate_since >= self.debounce:
            self._commit(oid, key, st, raw, st.candidate_since)

    def _commit(self, oid, key, st, state, start_ts):
        """oid = operator whose logic is used (idle reason), key = P-ID stored in the DB."""
        if st.since is not None:
            start_ts = max(start_ts, st.since)
        print(f"[STATUS] {self.camera_id} {key} ({oid} logic): {st.status} -> {state}")

        reason = (REASON_AWAY if state == AWAY
                  else self.ops[oid]["idle_reason"] if state == IDLE else None)
        try:
            if st.segment_id is not None:
                operator_db.close_segment(
                    st.segment_id, self._iso(start_ts), start_ts - st.since
                )
            st.segment_id = operator_db.open_segment(
                self._build_row(state, reason, datetime.fromtimestamp(start_ts), key)
            )
        except Exception as e:
            print(f"[ERROR] operator_status write failed: {e}")

        st.status = state
        st.since = start_ts
        st.candidate = None

    @staticmethod
    def _iso(ts):
        return datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")

    def _build_row(self, state, reason, start_dt, operator_id):
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
            "operator_id": operator_id,
            "plant": CONFIG.get("plant"),
        }

    # ---------------- drawing ----------------

    def _draw_pick(self, frame):
        pick = self._pick
        if pick is not None:
            x1, y1, x2, y2 = map(int, pick["box"])
            overlapping = pick["overlap"] >= self.pick_overlap_min
            color = COLOR_ACTIVE if overlapping else COLOR_YELLOW
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 6 if overlapping else 3)

            label = f"YELLOW ov={pick['overlap']:.2f}"
            if self.counter.locked:
                label += " (counted)"
            cv2.putText(frame, label, (x1, max(30, y1 - 12)), FONT, 1.0, color, 3)

        h = frame.shape[0]
        cv2.putText(
            frame,
            f"Units counted: {self.counter.total}   "
            f"overlap {self.counter.run}/{self.counter.overlap_frames}",
            (30, h - 40), FONT, 1.5, (255, 255, 255), 4,
        )

    def _draw(self, frame, persons, towels, bwts, near, wobjs, objects, boxes, now):
        self._draw_pick(frame)

        if self.debug_draw:
            for name, conf, box in self.raw:
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_DEBUG, 1)
                cv2.putText(frame, f"{name} {conf:.2f}",
                            (x1, min(frame.shape[0] - 5, y2 + 22)),
                            FONT, 0.7, COLOR_DEBUG, 2)

        # Station ROI (drawn for reference)
        if self.station_roi is not None:
            cv2.polylines(frame, [self.station_roi], True, (255, 255, 255), 2)

        # ROIs: yellow while waiting for a P-ID, thin grey once decided
        for oid, o in self.ops.items():
            b = self.bindings[oid]
            if b.gid is not None:
                st = self.state.get(f"P{b.gid}")
                tag, color, thick = f"{oid} -> P{b.gid}", COLOR_BOUND_ROI, 1
                if st is not None and st.status == AWAY:
                    tag, color = f"{tag} AWAY", COLOR_AWAY
            elif b.cand is not None:
                tag = f"{oid} P{b.cand}? {int(now - b.cand_since)}/{int(self.bind_seconds)}s"
                color, thick = COLOR_SEAT, 3
            else:
                tag, color, thick = f"{oid} (waiting)", COLOR_SEAT, 3
            cv2.polylines(frame, [o["roi"]], True, color, thick)
            cx, cy = o["centre"]
            cv2.putText(frame, tag, (int(cx) - 60, int(cy)), FONT, 0.9, color, 2)

        for ob in objects:
            x1, y1, x2, y2 = map(int, ob["box"])
            color = OBJECT_COLORS.get(ob["name"].lower(), (200, 200, 0))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Closed boxes (the counted class)
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

        for b in wobjs:
            if b["touched"]:
                x1, y1, x2, y2 = map(int, b["box"])
                cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_ACTIVE, 5)

        for t in towels:
            x1, y1, x2, y2 = map(int, t["box"])
            color = COLOR_ACTIVE if t["touched"] else OBJECT_COLORS["towel"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5 if t["touched"] else 2)

        # Tracked people who are not an operator right now (thin grey)
        assigned = {p["track_idx"] for p in persons}
        for i, t in enumerate(self.tracks):
            if i in assigned:
                continue
            x1, y1, x2, y2 = map(int, t["box"])
            tag = f"P{t['gid']}" if t["gid"] > 0 else f"? t{t['lid']}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_TRACK, 2)
            cv2.putText(frame, tag, (x1 + 4, y1 + 26), FONT, 0.8, COLOR_TRACK, 2)

        for p in persons:
            x1, y1, x2, y2 = map(int, p["box"])
            oid = p["op"]
            st = self.state.get(p["key"]) or OperatorState()
            who = f"{p['key']} [{oid}]"

            if st.status == ACTIVE:
                color, label = COLOR_ACTIVE, f"{who}  ACTIVE"
            elif st.status == IDLE:
                color, label = COLOR_IDLE, f"{who}  IDLE"
            else:
                color, label = COLOR_PENDING, f"{who}  ..."

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5)
            (tw, th), _ = cv2.getTextSize(label, FONT, 1.2, 3)
            top = max(0, y1 - th - 24)
            cv2.rectangle(frame, (x1, top), (x1 + tw + 20, top + th + 24), color, -1)
            cv2.putText(frame, label, (x1 + 10, top + th + 8),
                        FONT, 1.2, (0, 0, 0), 3)

            if p["kxy"] is not None:
                dot = COLOR_NO_POSE if not p["pose_ok"] else (
                    COLOR_ACTIVE if p["working"] else (0, 0, 255))
                wc = self.ops[oid]["wrist_conf"]
                for k in WRISTS:
                    if p["kconf"][k] > wc:
                        x, y = p["kxy"][k]
                        cv2.circle(frame, (int(x), int(y)), 10, dot, -1)