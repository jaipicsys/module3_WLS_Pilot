import os
import time

# Use TCP for RTSP and give up on a dead connection after 5 seconds
# (otherwise OpenCV can hang ~30s on an unreachable camera).
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;5000000",
)

import cv2

from config_utils import CONFIG
from logics import FrameLogic
from video_recorder import VideoRecorder

RETRY_SECONDS = CONFIG.get("rtsp_retry_seconds", 3)
RECORD_VIDEO = CONFIG.get("record_video", False)


class CameraWorker:
    def __init__(
        self,
        camera_id,
        rtsp_url,
        on_done_callback=None,
        enable_display=False,
        display_scale=0.6,
    ):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.on_done_callback = on_done_callback
        self.enable_display = enable_display
        self.display_scale = display_scale

        # All processing logic lives in logics.py
        self.logic = FrameLogic(camera_id)

        # Recording needs the annotations drawn, even without a display.
        self.recorder = None
        if RECORD_VIDEO:
            self.recorder = VideoRecorder(camera_id)
            self.logic.draw = True

    def _show(self, frame, window_name):
        """Show a frame. Returns False if the user pressed 'q'."""
        height, width = frame.shape[:2]

        display_frame = cv2.resize(
            frame,
            (
                max(1, int(width * self.display_scale)),
                max(1, int(height * self.display_scale)),
            ),
            interpolation=cv2.INTER_AREA,
        )

        cv2.imshow(window_name, display_frame)
        return (cv2.waitKey(1) & 0xFF) != ord("q")

    def run(self):
        print(f"[INFO] Camera processor initialized: {self.camera_id}")
        print(f"[INFO] RTSP URL: {self.rtsp_url}")
        print(f"[INFO] Display enabled: {self.enable_display}")
        print(f"[INFO] Display scale: {self.display_scale}")
        print(f"[INFO] Recording enabled: {RECORD_VIDEO}")
        print(f"[INFO] Reconnect interval: {RETRY_SECONDS}s")

        window_name = f"Camera - {self.camera_id}"
        stop = False

        try:
            while not stop:
                cap = cv2.VideoCapture(self.rtsp_url)

                if not cap.isOpened():
                    cap.release()
                    print(
                        f"[WARNING] {self.camera_id} not connected. "
                        f"Retrying in {RETRY_SECONDS}s..."
                    )
                    time.sleep(RETRY_SECONDS)
                    continue

                print(f"[INFO] {self.camera_id} connected.")

                try:
                    while True:
                        ret, frame = cap.read()

                        if not ret:
                            print(
                                f"[WARNING] Lost stream from "
                                f"{self.camera_id}. Reconnecting..."
                            )
                            break  # back to the outer loop and reconnect

                        output_frame = self.logic.process(frame)

                        if self.recorder is not None:
                            self.recorder.write(output_frame)

                        if self.enable_display:
                            if not self._show(output_frame, window_name):
                                stop = True
                                break
                finally:
                    cap.release()

                if not stop:
                    time.sleep(RETRY_SECONDS)

        finally:
            if self.recorder is not None:
                self.recorder.close()

            if self.enable_display:
                cv2.destroyAllWindows()

            print(f"[INFO] Camera processor stopped: {self.camera_id}")

            if self.on_done_callback:
                self.on_done_callback(self.camera_id)