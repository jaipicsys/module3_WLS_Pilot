"""
Live camera feed, shared between the camera workers and the Flask API.

The camera workers already read every RTSP stream, so the API does NOT open a
second connection. A worker hands each frame to the hub; the hub only encodes
a JPEG while someone is watching (or asked for a snapshot), capped at FPS
frames per second and MAX_WIDTH pixels wide. The browser shows the feed with a
plain <img src=".../api/camera/<id>/stream">. The RTSP URL (with its password)
never leaves the backend.
"""

import time
from threading import Lock

import cv2

FPS = 10              # frames per second sent to the browser
MAX_WIDTH = 960       # wider frames are scaled down
JPEG_QUALITY = 70
WANT_SECONDS = 5      # a snapshot request keeps encoding on for this long
ONLINE_SECONDS = 5    # camera counts as online if a frame arrived this recently


class FrameHub:
    def __init__(self):
        self._lock = Lock()
        self._jpeg = {}         # cam_id -> (jpeg bytes, time)
        self._beat = {}         # cam_id -> time of the last processed frame
        self._viewers = {}      # cam_id -> number of open streams
        self._want_until = {}   # cam_id -> keep encoding until this time
        self._last_encode = {}
        self.fps, self.max_width, self.quality = FPS, MAX_WIDTH, JPEG_QUALITY

    # ---------- called by the camera workers ----------

    def configure(self, fps=None, width=None, quality=None):
        self.fps = fps or self.fps
        self.max_width = width or self.max_width
        self.quality = quality or self.quality

    def register(self, cam_id):
        with self._lock:
            self._beat.setdefault(cam_id, 0.0)
            self._viewers.setdefault(cam_id, 0)

    def beat(self, cam_id):
        """Cheap: call for every processed frame."""
        self._beat[cam_id] = time.time()

    def wants(self, cam_id):
        """True while someone is watching or just asked for a snapshot."""
        return self._viewers.get(cam_id, 0) > 0 or time.time() < self._want_until.get(cam_id, 0.0)

    def publish(self, cam_id, frame):
        """Encode a frame (rate-limited). Call only when wants(cam_id)."""
        now = time.time()
        if now - self._last_encode.get(cam_id, 0.0) < 1.0 / self.fps:
            return
        self._last_encode[cam_id] = now

        height, width = frame.shape[:2]
        if width > self.max_width:
            frame = cv2.resize(
                frame,
                (self.max_width, max(1, int(height * self.max_width / width))),
                interpolation=cv2.INTER_AREA,
            )

        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        if ok:
            with self._lock:
                self._jpeg[cam_id] = (buffer.tobytes(), now)

    # ---------- called by the API ----------

    def known(self, cam_id):
        return cam_id in self._beat

    def cameras(self):
        now = time.time()
        return [
            {"id": cam_id, "online": now - beat <= ONLINE_SECONDS}
            for cam_id, beat in self._beat.items()
        ]

    def latest(self, cam_id):
        with self._lock:
            return self._jpeg.get(cam_id, (None, 0.0))

    def snapshot(self, cam_id, timeout=2.0):
        """One fresh JPEG (waits up to `timeout`); the last one if none arrives."""
        asked = time.time()
        self._want_until[cam_id] = asked + WANT_SECONDS
        while time.time() < asked + timeout:
            jpeg, stamp = self.latest(cam_id)
            if jpeg is not None and stamp >= asked:
                return jpeg
            time.sleep(0.05)
        return self.latest(cam_id)[0]

    def stream(self, cam_id):
        """MJPEG generator: yields one multipart chunk per new frame."""
        with self._lock:
            self._viewers[cam_id] = self._viewers.get(cam_id, 0) + 1
        try:
            started = last_sent = time.time()
            last_stamp = 0.0
            while True:
                jpeg, stamp = self.latest(cam_id)
                now = time.time()

                # New frame, or repeat the last one once a second. The repeat
                # makes a closed browser tab fail the write, so we notice it.
                if jpeg is not None and (stamp != last_stamp or now - last_sent >= 1.0):
                    last_stamp, last_sent = stamp, now
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(jpeg)).encode()
                        + b"\r\n\r\n" + jpeg + b"\r\n"
                    )
                elif jpeg is None and now - started > 10:
                    return  # camera never produced a frame
                else:
                    time.sleep(0.03)
        finally:
            with self._lock:
                self._viewers[cam_id] = max(0, self._viewers.get(cam_id, 1) - 1)


hub = FrameHub()