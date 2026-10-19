import math
from collections import deque

import cv2
import numpy as np


class BoxCounter:
    """
    Counts boxes that cross a line from the table side to the trolley side
    while a trolley is inside the zone.
    """

    NO_TROLLEY = "NO_TROLLEY"
    LOADING = "LOADING"

    def __init__(self, zone, line, full_count=12, margin_frac=0.12,
                 match_factor=1.0, max_missed_s=1.0, confirm_s=1.0,
                 absent_s=5.0, cooldown_s=5.0, extend=0.15):
        self.zone = np.array(zone, np.int32).reshape(-1, 1, 2)
        self.line = line

        (x1, y1), (x2, y2), (tx, ty) = line
        self.p1 = (float(x1), float(y1))
        self.d = (float(x2 - x1), float(y2 - y1))
        self.length = math.hypot(*self.d)
        if self.length < 1.0:
            raise ValueError("line endpoints must be different points")
        raw = self._raw(tx, ty)
        if abs(raw) < 1e-6:
            raise ValueError("the trolley-side point must not lie on the line")
        self.sign = 1.0 if raw > 0 else -1.0     # trolley side becomes positive

        self.full_count = full_count
        self.margin_frac = margin_frac
        self.match_factor = match_factor
        self.max_missed_s = max_missed_s
        self.confirm_s = confirm_s
        self.absent_s = absent_s
        self.cooldown_s = cooldown_s
        self.extend = extend

        self.state = self.NO_TROLLEY
        self.on_trolley = 0         # boxes counted on the current trolley
        self.total = 0              # boxes counted since start
        self.sets = 0               # full trolleys since start

        self.tracks = []
        self._next_id = 1
        self._first_seen = None     # trolley continuously seen since
        self._last_seen = None      # trolley last seen
        self._last_count = -1e9
        self._flash_until = 0.0

    # ---------------- public ----------------

    def update(self, now, trolleys, boxes):
        """Call every frame. Returns how many boxes were newly counted."""
        self._update_cycle(now, trolleys)
        crossed = self._update_tracks(now, boxes)

        counted = 0
        if self.state == self.LOADING:
            for _ in crossed:
                if self.on_trolley >= self.full_count:
                    break
                if now - self._last_count < self.cooldown_s:
                    continue
                self.on_trolley += 1
                self.total += 1
                self._last_count = now
                self._flash_until = now + 0.7
                counted += 1
        return counted

    def reset_tracks(self):
        """Call after the stream dropped: forget partly tracked boxes."""
        self.tracks = []

    # ---------------- trolley cycle ----------------

    def _in_zone(self, b):
        base = ((b[0] + b[2]) / 2.0, float(b[3]))
        centre = ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)
        return any(cv2.pointPolygonTest(self.zone, p, False) >= 0
                   for p in (base, centre))

    def _update_cycle(self, now, trolleys):
        present = any(self._in_zone(t) for t in trolleys)

        if present:
            if self._first_seen is None:
                self._first_seen = now
            self._last_seen = now
            if (self.state == self.NO_TROLLEY
                    and now - self._first_seen >= self.confirm_s):
                self.state = self.LOADING
                self.on_trolley = 0
            return

        if self._last_seen is None:
            return
        gap = now - self._last_seen

        if self.state == self.LOADING and gap >= self.absent_s:
            if self.on_trolley >= self.full_count:
                self.sets += 1
            self.state = self.NO_TROLLEY
            self.on_trolley = 0
            self._first_seen = None
        elif self.state == self.NO_TROLLEY and gap > 0.5:
            self._first_seen = None

    # ---------------- line geometry ----------------

    def _raw(self, x, y):
        return (self.d[0] * (y - self.p1[1]) - self.d[1] * (x - self.p1[0])) / self.length

    def _sd(self, x, y):
        """Signed distance to the line: > 0 trolley side, < 0 table side."""
        return self._raw(x, y) * self.sign

    def _within_extent(self, x, y):
        u = ((x - self.p1[0]) * self.d[0] + (y - self.p1[1]) * self.d[1]) / (self.length ** 2)
        return -self.extend <= u <= 1.0 + self.extend

    # ---------------- box tracking ----------------

    def _update_tracks(self, now, boxes):
        dets = [((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0, max(b[2] - b[0], 1.0))
                for b in boxes]

        pairs = []
        for ti, t in enumerate(self.tracks):
            for di, (cx, cy, w) in enumerate(dets):
                dist = math.hypot(cx - t["cx"], cy - t["cy"])
                if dist <= self.match_factor * max(t["w"], w):
                    pairs.append((dist, ti, di))
        pairs.sort()

        used_t, used_d, touched = set(), set(), []
        for _, ti, di in pairs:
            if ti in used_t or di in used_d:
                continue
            used_t.add(ti)
            used_d.add(di)
            t = self.tracks[ti]
            t["cx"], t["cy"], t["w"] = dets[di]
            t["seen"] = now
            t["trail"].append((t["cx"], t["cy"]))
            touched.append(t)

        for di, (cx, cy, w) in enumerate(dets):
            if di in used_d:
                continue
            t = {"id": self._next_id, "cx": cx, "cy": cy, "w": w, "seen": now,
                 "armed": False, "fired": False, "trail": deque([(cx, cy)], maxlen=40)}
            self._next_id += 1
            self.tracks.append(t)
            touched.append(t)

        self.tracks = [t for t in self.tracks if now - t["seen"] <= self.max_missed_s]

        return [t for t in touched if self._crossed(t)]

    def _crossed(self, t):
        if t["fired"]:
            return False

        sd = self._sd(t["cx"], t["cy"])
        margin = max(3.0, self.margin_frac * t["w"])

        if sd <= -margin:                       # table side: arm it
            t["armed"] = True
            return False

        if t["armed"] and sd >= margin:         # crossed to the trolley side
            if self._within_extent(t["cx"], t["cy"]):
                t["fired"] = True
                return True
            t["armed"] = False                  # went around the end of the line
        return False

    # ---------------- overlay ----------------

    def draw(self, frame, now):
        cv2.polylines(frame, [self.zone], True, (255, 200, 0), 3)

        (x1, y1), (x2, y2), (tx, ty) = self.line
        col = (0, 0, 255) if now < self._flash_until else (255, 0, 255)
        cv2.line(frame, (x1, y1), (x2, y2), col, 5 if col[2] == 255 and col[0] == 0 else 3)

        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        n = self.length
        nx, ny = -self.d[1] / n, self.d[0] / n
        if (tx - mx) * nx + (ty - my) * ny < 0:
            nx, ny = -nx, -ny
        cv2.arrowedLine(frame, (int(mx), int(my)),
                        (int(mx + nx * 45), int(my + ny * 45)), col, 3, tipLength=0.4)

        for t in self.tracks:
            c = (0, 0, 255) if t["fired"] else (0, 255, 0) if t["armed"] else (160, 160, 160)
            if len(t["trail"]) > 1:
                cv2.polylines(frame, [np.array(t["trail"], np.int32)], False, c, 2)
            cv2.circle(frame, (int(t["cx"]), int(t["cy"])), 6, c, -1)

        h = frame.shape[0]
        cv2.putText(
            frame,
            f"{self.state}  on trolley {self.on_trolley}/{self.full_count}  "
            f"total {self.total}  sets {self.sets}",
            (30, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 4,
        )