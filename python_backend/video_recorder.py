import atexit
import os
import signal
import sys
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


def _install_sigterm_close():
    """`kill <pid>` / systemd stop send SIGTERM, which skips atexit: the last segment was then
    never finalised (cut-off / unplayable video). Close the recorders first, then exit."""
    try:
        if signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL:
            return  # the app already handles SIGTERM itself
        def _handler(signum, frame):
            close_all_recorders()
            sys.exit(0)
        signal.signal(signal.SIGTERM, _handler)
    except (ValueError, OSError):  # not the main thread / unsupported platform
        pass


_install_sigterm_close()


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
        # DEFAULT (both False) = the ORIGINAL behaviour: at most one frame per 1/record_fps seconds,
        # segments rotate by clock time. Nothing below changes RTSP recordings unless you switch it on.
        # record_realtime  true : the video keeps REAL-TIME duration - gaps are filled by repeating the
        #                         last frame, so playback is not sped up when processing is slower than
        #                         record_fps (the file then holds repeated frames).
        # every_frame      true : (video-file tests) every processed frame is written, none skipped/repeated.
        self.realtime = CONFIG.get("record_realtime", False)
        self.every_frame = CONFIG.get("record_every_frame", False)
        # A stall longer than this (e.g. a reconnect) is not padded with frozen frames.
        self.max_gap_s = CONFIG.get("record_max_gap_seconds", 5)

        self.out_dir = os.path.join(
            BASE_DIR, CONFIG.get("record_dir", "recordings"), camera_id
        )
        os.makedirs(self.out_dir, exist_ok=True)

        self.writer = None
        self.size = None
        self.segment_start = 0.0
        self.last_write = 0.0
        self.frames_written = 0
        self.lock = threading.Lock()

        _recorders.append(self)

    def configure(self, every_frame=None, fps=None, realtime=None):
        """Called by the worker when a VIDEO FILE source connects. RTSP passes nothing (None) and
        therefore keeps the configured / original behaviour."""
        with self.lock:
            changed = False
            if every_frame is not None and every_frame != self.every_frame:
                self.every_frame, changed = every_frame, True
            if realtime is not None and realtime != self.realtime:
                self.realtime, changed = realtime, True
            if fps and abs(fps - self.fps) > 0.01:
                self.fps, changed = float(fps), True
            if changed:
                self._release()  # next frame opens a new segment with the new settings

    def write(self, frame):
        now = time.time()
        if self.realtime or self.every_frame:
            return self._write_paced(frame, now)

        # ---- ORIGINAL behaviour (default) ----
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
                self.frames_written += 1

    def _write_paced(self, frame, now):
        """record_realtime / every_frame: see the options in __init__."""
        h0, w0 = frame.shape[:2]
        w, h = (int(w0 * self.scale), int(h0 * self.scale)) if self.scale != 1.0 else (w0, h0)

        with self.lock:
            # New segment on first frame, time limit (in VIDEO time), or resolution change.
            if (
                self.writer is None
                or self.size != (w, h)
                or self.frames_written / self.fps >= self.segment_seconds
            ):
                self._open(w, h, now)
            if self.writer is None:
                return

            if self.every_frame:
                repeats = 1
            else:
                # Frames the video should hold by now, to match wall-clock time.
                repeats = int((now - self.segment_start) * self.fps) + 1 - self.frames_written
                if repeats <= 0:
                    return  # arriving faster than record fps: skip, keep real-time speed
                if repeats > self.max_gap_s * self.fps:  # long stall: don't pad minutes of video
                    self.segment_start += (repeats - 1) / self.fps
                    repeats = 1

            if self.scale != 1.0:
                frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
            for _ in range(repeats):
                self.writer.write(frame)
            self.frames_written += repeats

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
        self.path = path
        self.size = (w, h)
        self.frames_written = 0
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
            print(f"[REC] {self.camera_id}: closed {os.path.basename(getattr(self, 'path', '?'))} "
                  f"({self.frames_written} frames = {self.frames_written / self.fps:.0f}s of video)")

    def close(self):
        with self.lock:
            self._release()