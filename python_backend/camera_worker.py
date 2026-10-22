import os
import time
from datetime import datetime

# Use TCP for RTSP and give up on a dead connection after 5 seconds
# (otherwise OpenCV can hang ~30s on an unreachable camera).
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;5000000",
)

import cv2

import operator_db
from config_utils import CONFIG
from logics import FrameLogic, OperatorState, _cam_number
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

        # Time of the last frame that was processed (None = none since last close).
        self.last_frame_time = None

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

    def _close_open_rows(self):
        """
        The camera ended: write the last frame's time into every open
        operator_status row of this camera (end_time + durations).
        """
        if self.last_frame_time is None:
            return  # nothing processed since the last close

        try:
            closed = operator_db.close_open_segments(
                _cam_number(self.camera_id), self.last_frame_time
            )

            self.logic.on_stream_gap()  # resets the unit counter

            # Forget the closed rows, so after a reconnect each operator
            # starts a fresh row instead of editing an old one.
            self.logic.state = {oid: OperatorState() for oid in self.logic.ops}

            if closed:
                print(
                    f"[INFO] {self.camera_id}: closed {closed} open "
                    f"operator_status row(s) at {self.last_frame_time:%H:%M:%S}"
                )
        except Exception as e:
            print(f"[ERROR] {self.camera_id}: closing open rows failed: {e}")

        self.last_frame_time = None

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
                            self._close_open_rows()
                            break  # back to the outer loop and reconnect

                        output_frame = self.logic.process(frame)
                        self.last_frame_time = datetime.now()

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
            # 'q' pressed or an error: also close open rows (does nothing if the
            # stream-loss branch already did).
            self._close_open_rows()

            if self.recorder is not None:
                self.recorder.close()

            if self.enable_display:
                cv2.destroyAllWindows()

            print(f"[INFO] Camera processor stopped: {self.camera_id}")

            if self.on_done_callback:
                self.on_done_callback(self.camera_id)