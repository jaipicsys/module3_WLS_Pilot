import os
import subprocess
import sys
import time
from threading import Lock, Thread
from logics import CameraProcessor

class CameraManager:
    def __init__(
        self,
        camera_config,
        enable_display=False,
        display_scale=0.6,
    ):
        self.processors = {}
        self.threads = {}
        self._restart_lock = Lock()
        self._restart_started = False

        for cam_id, rtsp_url in camera_config.items():
            processor = CameraProcessor(
                camera_id=cam_id,
                rtsp_url=rtsp_url,
                on_done_callback=self.on_camera_done,
                enable_display=enable_display,
                display_scale=display_scale,
            )

            self.processors[cam_id] = processor
            self.threads[cam_id] = Thread(
                target=processor.run,
                daemon=True,
                name=f"camera-{cam_id}",
            )

    def on_camera_done(self, camera_id):
        print(
            f"[INFO] Camera {camera_id} processing completed."
        )
        self.restart_server()

    def restart_server(self):
        # Prevent multiple camera threads from restarting simultaneously.
        with self._restart_lock:
            if self._restart_started:
                return

            self._restart_started = True

        print("[INFO] Restarting server in 1 second...")
        time.sleep(1)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.join(script_dir, "app.py")

        if sys.argv[0].endswith("app.py"):
            print("[INFO] Restarting Python application.")
            subprocess.Popen(
                [sys.executable, app_path],
                cwd=script_dir,
            )

        elif sys.argv[0].endswith("app.bin"):
            print("[INFO] Restarting binary application.")
            subprocess.Popen(
                [os.path.join(script_dir, "app.bin")],
                cwd=script_dir,
            )

        else:
            print(
                "[ERROR] Unknown application mode. "
                "Server was not restarted."
            )
            self._restart_started = False
            return

        os._exit(0)

    def start_all(self):
        for cam_id, thread in self.threads.items():
            print(f"[INFO] Starting camera {cam_id}...")
            thread.start()
