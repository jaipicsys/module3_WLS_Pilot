class CameraProcessor:
    def __init__(
        self,
        camera_id,
        rtsp_url,
        on_done_callback=None,
    ):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.on_done_callback = on_done_callback

    def run(self):
        print(
            f"[INFO] Camera processor initialized: "
            f"{self.camera_id}"
        )
        print(f"[INFO] RTSP URL: {self.rtsp_url}")

        # Add camera-processing logic here later.
        # Do not invoke on_done_callback here until you
        # have implemented the intended completion condition.
