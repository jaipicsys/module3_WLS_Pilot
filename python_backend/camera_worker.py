import cv2

from logics import FrameLogic


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

    def run(self):
        print(
            f"[INFO] Camera processor initialized: "
            f"{self.camera_id}"
        )
        print(f"[INFO] RTSP URL: {self.rtsp_url}")
        print(f"[INFO] Display enabled: {self.enable_display}")
        print(f"[INFO] Display scale: {self.display_scale}")

        cap = cv2.VideoCapture(self.rtsp_url)

        if not cap.isOpened():
            print(
                f"[ERROR] Could not open camera "
                f"{self.camera_id}"
            )
            cap.release()
            return

        window_name = f"Camera - {self.camera_id}"

        try:
            while True:
                ret, frame = cap.read()

                if not ret:
                    print(
                        f"[WARNING] Failed to read frame "
                        f"from {self.camera_id}"
                    )
                    break

                # Hand the frame to the logic layer.
                output_frame = self.logic.process(frame)

                if self.enable_display:
                    height, width = output_frame.shape[:2]

                    new_width = max(
                        1, int(width * self.display_scale)
                    )
                    new_height = max(
                        1, int(height * self.display_scale)
                    )

                    display_frame = cv2.resize(
                        output_frame,
                        (new_width, new_height),
                        interpolation=cv2.INTER_AREA,
                    )

                    cv2.imshow(window_name, display_frame)

                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

        finally:
            cap.release()

            if self.enable_display:
                cv2.destroyWindow(window_name)

            print(
                f"[INFO] Camera processor stopped: "
                f"{self.camera_id}"
            )

            if self.on_done_callback:
                self.on_done_callback(self.camera_id)