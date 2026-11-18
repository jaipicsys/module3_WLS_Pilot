"""
TrackingLogic: drop-in replacement for FrameLogic while we focus on tracking.

CameraWorker calls   frame = logic.process(frame)   and the recorder saves that frame, so the
recording shows YOLOv8n + BoT-SORT + OSNet ReID: P-id boxes with appearance distance, a status
bar, and banners when a person is NEW / LOST / RELINKED.
No operator logic, no DB writes, no unit counting here (added back later).
"""
import time

import cv2
import numpy as np

from config_utils import CONFIG
from .person_tracker import PersonTracker

FONT = cv2.FONT_HERSHEY_SIMPLEX
BANNER_SECONDS = 4
EVENT_COLORS = {"NEW": (0, 255, 255), "LOST": (60, 60, 255), "RELINK": (0, 255, 0),
                "UNKNOWN": (0, 165, 255), "SUSPECT": (0, 0, 255)}


def _color(gid):
    if gid is None or gid < 0:
        return (160, 160, 160)
    rng = np.random.RandomState(gid * 7919 % (2**32 - 1))
    return tuple(int(v) for v in rng.randint(60, 255, 3))


class TrackingLogic:
    def __init__(self, camera_id, **overrides):
        self.camera_id = camera_id
        self.draw = True
        self.ops = {}
        self.state = {}
        self.tracker = PersonTracker(camera_id, **overrides)
        cfg = CONFIG.get("person_tracking", {})
        self.rois = self._load_rois() if cfg.get("draw_rois", False) else []   # operator ROIs (optional)
        self.draw_outside = cfg.get("draw_outside_people", False)
        self._seen_events = 0
        self._banners = []

    @staticmethod
    def _load_rois():
        polys = []
        for line in CONFIG.get("lines", {}).values():
            for st in line.get("stations", {}).values():
                for op in st.get("operators", {}).values():
                    if op.get("roi"):
                        polys.append(np.array(op["roi"], np.int32).reshape(-1, 1, 2))
        return polys

    def on_stream_gap(self):
        self.tracker.reset()
        self._seen_events = len(self.tracker.events)
        self._banners.clear()

    def process(self, frame):
        tracks = self.tracker.update(frame)
        for _, _, kind, gid, extra in self.tracker.events[self._seen_events:]:
            if kind in EVENT_COLORS:
                who = f"P{gid}" if gid > 0 else ""
                self._banners.append((time.time() + BANNER_SECONDS,
                                      f"{who} {kind} {extra}".strip()[:70], EVENT_COLORS[kind]))
        self._seen_events = len(self.tracker.events)
        if self.draw:
            self._draw(frame, tracks)
        return frame

    def _draw(self, frame, tracks):
        for p in self.rois:
            cv2.polylines(frame, [p], True, (90, 90, 90), 1)

        roi = self.tracker.roi
        if roi is not None:                      # the focus area: tinted fill + thick outline
            overlay = frame.copy()
            cv2.fillPoly(overlay, [roi], (0, 200, 255))
            cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)
            cv2.polylines(frame, [roi], True, (0, 200, 255), 3)
            x0, y0 = int(roi[0, 0, 0]), int(roi[0, 0, 1])
            cv2.putText(frame, "ROI", (x0 + 6, y0 - 10), FONT, 1.0, (0, 200, 255), 3)

        for t in tracks:
            if t["state"] == "outside":          # not in the ROI: ignored (optionally a thin grey box)
                if self.draw_outside:
                    x1, y1, x2, y2 = map(int, t["box"])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (110, 110, 110), 1)
                continue
            x1, y1, x2, y2 = map(int, t["box"])
            c = _color(t["id"])
            cv2.rectangle(frame, (x1, y1), (x2, y2), c, 4)
            if t["id"] > 0:
                label = f"P{t['id']}" + (f"  d={t['dist']:.2f}" if t["dist"] is not None else "")
                if t["state"] == "relinked":
                    label += "  RELINK"
            else:
                label = f"? t{t['tid']} {t['state']}"
                if t["dist"] is not None:
                    label += f" d={t['dist']:.2f}"
            (tw, th), _ = cv2.getTextSize(label, FONT, 1.0, 3)
            cv2.rectangle(frame, (x1, max(0, y1 - th - 14)), (x1 + tw + 8, y1), c, -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 7), FONT, 1.0, (0, 0, 0), 3)

        s = self.tracker.summary()
        n_in = sum(1 for t in tracks if t["state"] != "outside")
        hud = (f"YOLOv8n + BoT-SORT + OSNet ReID {s['reid']} | in ROI {n_in} | "
               f"known {s['people_known']} | relinks {s['relinks']}")
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), (0, 0, 0), -1)
        cv2.putText(frame, hud, (12, 36), FONT, 1.0, (0, 255, 0), 2)

        # frame number + clock, burned into the picture (this is the number used in the logs / csv)
        stamp = f"FRAME {self.tracker.frame_no}   {time.strftime('%H:%M:%S')}"
        (tw, th), _ = cv2.getTextSize(stamp, FONT, 1.4, 4)
        x = frame.shape[1] - tw - 20
        cv2.rectangle(frame, (x - 10, 55), (frame.shape[1], 55 + th + 24), (0, 0, 0), -1)
        cv2.putText(frame, stamp, (x, 55 + th + 8), FONT, 1.4, (255, 255, 255), 4)

        now = time.time()
        self._banners = [b for b in self._banners if b[0] > now][-6:]
        for i, (_, text, color) in enumerate(self._banners):
            cv2.putText(frame, text, (12, 100 + i * 42), FONT, 1.0, color, 3)