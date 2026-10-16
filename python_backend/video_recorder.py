import atexit
import os
import threading
import time
from datetime import datetime, timedelta

import cv2

from config_utils import BASE_DIR, CONFIG

_recorders = []


def close_all_recorders():
    for r in list(_recorders):
        r.close()


# Runs on normal exit and after Ctrl+C is caught in app.py.
atexit.register(close_all_recorders)


class VideoRecorder:
    """Writes annotated frames to rolling video segments for one camera."""

    def __init__(self, camera_id):
        self.camera_id = camera_id

        self.fps = CONFIG.get("record_fps", 10)
        self.scale = CONFIG.get("record_scale", 0.5)
        self.segment_seconds = CONFIG.get("record_segment_minutes", 10) * 60
        self.codec = CONFIG.get("record_codec", "MJPG")
        self.ext = CONFIG.get("record_ext", "avi")
        self.retention_days = CONFIG.get("record_retention_days", 7)

        self.out_dir = os.path.join(
            BASE_DIR, CONFIG.get("record_dir", "recordings"), camera_id
        )
        os.makedirs(self.out_dir, exist_ok=True)

        self.writer = None
        self.size = None
        self.segment_start = 0.0
        self.last_write = 0.0
        self.lock = threading.Lock()

        _recorders.append(self)

    def write(self, frame):
        now = time.time()

        # Cap the recording FPS so playback matches real time.
        if now - self.last_write < 1.0 / self.fps:
            return
        self.last_write = now

        if self.scale != 1.0:
            frame = cv2.resize(
                frame, None, fx=self.scale, fy=self.scale,
                interpolation=cv2.INTER_AREA,
            )

        h, w = frame.shape[:2]

        with self.lock:
            # New segment on first frame, time limit, or resolution change.
            if (
                self.writer is None
                or self.size != (w, h)
                or now - self.segment_start >= self.segment_seconds
            ):
                self._open(w, h, now)

            if self.writer is not None:
                self.writer.write(frame)

    def _open(self, w, h, now):
        self._release()

        name = f"{self.camera_id}_{datetime.now():%Y%m%d_%H%M%S}.{self.ext}"
        path = os.path.join(self.out_dir, name)

        writer = cv2.VideoWriter(
            path, cv2.VideoWriter_fourcc(*self.codec), self.fps, (w, h)
        )

        if not writer.isOpened():
            print(f"[ERROR] {self.camera_id}: cannot open video writer: {path}")
            self.writer = None
            return

        self.writer = writer
        self.size = (w, h)
        self.segment_start = now
        print(f"[REC] {self.camera_id}: recording to {path}")

        self._cleanup()

    def _cleanup(self):
        """Delete segments older than the retention period."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for fname in os.listdir(self.out_dir):
            if not fname.endswith(f".{self.ext}"):
                continue
            path = os.path.join(self.out_dir, fname)
            try:
                if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                    os.remove(path)
                    print(f"[REC] Deleted old recording: {fname}")
            except OSError:
                pass

    def _release(self):
        if self.writer is not None:
            self.writer.release()
            self.writer = None

    def close(self):
        with self.lock:
            self._release()