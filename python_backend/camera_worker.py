import os
import queue
import signal
import threading
import time
import traceback
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
from frame_hub import hub
from logics import FrameLogic, OperatorState, _cam_number
from video_recorder import VideoRecorder
import track_people_osnet_frozen as tp

RETRY_SECONDS = CONFIG.get("rtsp_retry_seconds", 3)
RECORD_VIDEO = CONFIG.get("record_video", False)

# ---- video FILE as a source (put a file path instead of rtsp:// in config.json). RTSP is unaffected. ----
# "file_playback": "realtime"    (default) plays the file ONCE at its own frame rate = normal speed, like a
#                                camera would deliver it. If the machine is busy, frames are skipped exactly
#                                like on RTSP (the [FPS] line shows the drop rate).
#                  "every_frame" no frame is skipped (repeatable test runs); never faster than normal speed,
#                                but slower when the machine cannot keep up.
# "file_loop": false (default)   play once; true = start again at the end (the old behaviour).
# "file_exit_when_done": true    when every source is a file and all have finished, close the app by itself
#                                (same as pressing Ctrl+C).
_URL_PREFIXES = ("rtsp://", "rtmp://", "http://", "https://")
FILE_PLAYBACK = str(CONFIG.get("file_playback", "realtime")).lower()
if FILE_PLAYBACK not in ("realtime", "every_frame"):
    print(f"[WARNING] file_playback '{FILE_PLAYBACK}' unknown, using 'realtime'")
    FILE_PLAYBACK = "realtime"
FILE_LOOP = bool(CONFIG.get("file_loop", False))
FILE_EXIT_WHEN_DONE = bool(CONFIG.get("file_exit_when_done", True))
_FILE_WORKERS = set()          # camera ids that are currently playing a file
_FILE_LOCK = threading.Lock()

# Optional "live_feed" block in config.json: {"fps": 10, "width": 960, "quality": 70}
LIVE_FEED = CONFIG.get("live_feed", {})
hub.configure(LIVE_FEED.get("fps"), LIVE_FEED.get("width"), LIVE_FEED.get("quality"))


def _release_reader(reader):
    """Stop a tp.RTSPReader without releasing the capture while its thread is
    still inside cap.read() (that race segfaults OpenCV/FFmpeg)."""
    reader.stopped = True
    reader.t.join(timeout=15)
    if reader.t.is_alive():
        print("[WARNING] RTSP reader thread did not stop; skipping release to avoid a crash")
        return
    reader.cap.release()


class FileReader:
    """TEST ONLY ("file_playback": "every_frame"): reads a video file frame by frame, nothing dropped
    (like the standalone script on an .mp4), but never faster than the file's own frame rate."""

    is_file = True

    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open {path}")
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self._dt = 1.0 / (fps if 1 <= fps <= 120 else 25.0)
        self._next = None
        self.ended = False
        self.stopped = False
        self.t = threading.Thread(target=lambda: None)  # so _release_reader() works
        self.t.start()

    def read(self):
        now = time.perf_counter()
        if self._next is not None and now < self._next:   # normal speed: wait for this frame's time
            time.sleep(self._next - now)
            now = self._next
        self._next = now + self._dt                        # if the machine is slower: no catch-up burst
        ok, frame = self.cap.read()
        if not ok:
            self.ended = True
            return False, None
        return True, frame

    def get(self, prop):
        return self.cap.get(prop)


class PacedFileReader:
    """Plays a video file ONCE at its own frame rate (normal speed), like a camera delivering it.
    Same latest-frame behaviour as tp.RTSPReader: if the tracker is still busy, the older frame is
    replaced (counted in .dropped)."""

    is_file = True

    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open {path}")
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self._dt = 1.0 / (fps if 1 <= fps <= 120 else 25.0)
        self.q = queue.Queue(maxsize=1)
        self.stopped = False
        self.ended = False
        self.received = 0
        self.dropped = 0
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()

    def _run(self):
        nxt = time.perf_counter()
        while not self.stopped:
            ok, f = self.cap.read()
            if not ok:
                break
            self.received += 1
            if self.q.full():
                try:
                    self.q.get_nowait()
                    self.dropped += 1
                except queue.Empty:
                    pass
            self.q.put(f)
            nxt += self._dt
            wait = nxt - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            else:
                nxt = time.perf_counter()
        self.ended = True

    def read(self):
        while True:
            try:
                return True, self.q.get(timeout=0.2)
            except queue.Empty:
                if (self.ended and self.q.empty()) or self.stopped:
                    return False, None

    def get(self, prop):
        return self.cap.get(prop)


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

        hub.register(camera_id)

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
        file_finished = False
        is_file_source = not str(self.rtsp_url).lower().startswith(_URL_PREFIXES)
        if is_file_source:
            with _FILE_LOCK:
                _FILE_WORKERS.add(self.camera_id)

        try:
            while not stop:
                try:
                    # Same background latest-frame reader as the independent tracker.
                    if str(self.rtsp_url).lower().startswith(_URL_PREFIXES):
                        cap = tp.RTSPReader(self.rtsp_url)
                    elif FILE_PLAYBACK == "every_frame":
                        cap = FileReader(self.rtsp_url)       # test: video file, every frame
                    else:
                        cap = PacedFileReader(self.rtsp_url)  # test: video file, normal speed
                except Exception as exc:
                    print(
                        f"[WARNING] {self.camera_id} not connected ({exc}). "
                        f"Retrying in {RETRY_SECONDS}s..."
                    )
                    time.sleep(RETRY_SECONDS)
                    continue

                source_fps = cap.get(cv2.CAP_PROP_FPS)
                self.logic.tracker.set_source_fps(source_fps)
                lockstep = isinstance(cap, FileReader)       # "every_frame" file mode only
                file_src = getattr(cap, "is_file", False)    # a video file (never True for RTSP)
                if self.recorder is not None and hasattr(self.recorder, "configure"):
                    # VIDEO FILES only. every_frame file test: write EVERY frame at the source fps.
                    # realtime file playback: keep real-time duration. RTSP passes nothing (None),
                    # so its recording keeps the configured / original behaviour.
                    try:
                        self.recorder.configure(
                            every_frame=True if lockstep else None,
                            fps=self.logic.tracker.fps if lockstep else None,
                            realtime=True if (file_src and not lockstep) else None)
                    except TypeError:   # an older video_recorder.py without the 'realtime' option
                        self.recorder.configure(
                            every_frame=True if lockstep else None,
                            fps=self.logic.tracker.fps if lockstep else None)
                elif self.recorder is not None and not getattr(self, "_warned_old_recorder", False):
                    self._warned_old_recorder = True
                    print(f"[WARNING] {self.camera_id}: video_recorder.py is an older version (no configure()). "
                          "Recording works with its old behaviour; please replace it with the latest file.")
                print(
                    f"[INFO] {self.camera_id} connected "
                    f"(source FPS={self.logic.tracker.fps:.2f}, "
                    f"{'video file, ' + FILE_PLAYBACK if file_src else 'latest-frame reader'})."
                )

                n_frames, t_start = 0, time.time()
                box = {"pair": None, "seq": 0, "lost": False, "taken": 0}
                cond = threading.Condition()
                stop_evt = threading.Event()

                def track_loop(cap=cap, box=box, cond=cond, stop_evt=stop_evt, is_file=lockstep):
                    # Tracker sees every frame it can handle, like the standalone script.
                    while not stop_evt.is_set():
                        ret, frame = cap.read()
                        if not ret:
                            with cond:
                                box["lost"] = True
                                cond.notify_all()
                            return
                        hub.beat(self.camera_id)
                        if hub.wants(self.camera_id):
                            hub.publish(self.camera_id, frame)
                        try:
                            tracks = self.logic.tracker.update(frame)
                        except Exception as exc:
                            print(f"[ERROR] {self.camera_id} tracker: {exc}")
                            continue
                        with cond:
                            box["pair"] = (frame, tracks)
                            box["seq"] += 1
                            cond.notify_all()
                            if is_file:
                                # File test: wait until the drawing/recording loop has taken this
                                # frame, so no frame is overwritten (live streams stay real-time).
                                cond.wait_for(
                                    lambda: box["taken"] == box["seq"] or stop_evt.is_set(),
                                    timeout=60)

                tracker_thread = threading.Thread(
                    target=track_loop, daemon=True, name=f"track-{self.camera_id}")
                tracker_thread.start()
                last_seq = 0

                try:
                    while True:
                        with cond:
                            cond.wait_for(
                                lambda: box["seq"] != last_seq or box["lost"], timeout=10)
                            lost = box["seq"] == last_seq  # lost stream or timeout
                            if not lost:
                                frame, tracks = box["pair"]
                                last_seq = box["seq"]
                                box["taken"] = last_seq
                                cond.notify_all()

                        if lost and file_src and cap.ended:
                            # A video FILE reached its end (not a lost stream).
                            print(f"[INFO] {self.camera_id}: video file finished after "
                                  f"{self.logic.tracker.frame_idx} frames"
                                  + (" - starting again (file_loop)." if FILE_LOOP
                                     else " - played once, stopping."))
                            self._close_open_rows()
                            if not FILE_LOOP:
                                file_finished = True
                                stop = True
                            break

                        if lost:
                            print(
                                f"[WARNING] Lost stream from "
                                f"{self.camera_id}. Reconnecting..."
                            )
                            self._close_open_rows()
                            break

                        output_frame = self.logic.process(frame, tracks)
                        self.last_frame_time = datetime.now()

                        n_frames += 1
                        if n_frames % 100 == 0:
                            rx = getattr(cap, "received", 0)
                            drop = (f", dropped {100 * cap.dropped / rx:.1f}% of stream frames"
                                    if rx else "")
                            print(f"[FPS] {self.camera_id}: logic "
                                  f"{n_frames / (time.time() - t_start):.1f} fps, "
                                  f"tracker {self.logic.tracker.frame_idx} frames total{drop}")
                            n_frames, t_start = 0, time.time()

                        if self.recorder is not None:
                            self.recorder.write(output_frame)

                        if self.enable_display:
                            if not self._show(output_frame, window_name):
                                stop = True
                                break
                except Exception:
                    traceback.print_exc()
                    print(f"[ERROR] {self.camera_id}: processing failed, reconnecting...")
                    self._close_open_rows()
                finally:
                    stop_evt.set()
                    with cond:
                        cond.notify_all()  # wake a tracker thread waiting for the main loop
                    tracker_thread.join(timeout=10)
                    _release_reader(cap)
                    try:
                        self.logic.tracker.write_summary()
                    except Exception as exc:  # noqa: BLE001
                        print(f"[WARNING] {self.camera_id}: tracking summary failed: {exc}")

                if not stop:
                    time.sleep(RETRY_SECONDS)

        except Exception:
            if not is_file_source:
                raise  # RTSP: unchanged - the exception propagates and the restart logic runs as before
            traceback.print_exc()
            print(f"[ERROR] {self.camera_id}: playing the video file failed (traceback above). "
                  "The application is NOT restarted, that would only repeat the error.")
        finally:
            # 'q' pressed or an error: also close open rows (does nothing if the
            # stream-loss branch already did).
            self._close_open_rows()

            if self.recorder is not None:
                self.recorder.close()

            if self.enable_display:
                cv2.destroyAllWindows()

            print(f"[INFO] Camera processor stopped: {self.camera_id}")

            with _FILE_LOCK:
                _FILE_WORKERS.discard(self.camera_id)
                other_files_running = bool(_FILE_WORKERS)

            if file_finished:
                # A finished video file must NOT trigger the "restart the server" callback
                # (it would start the file again in a new process).
                all_files = all(not str(u).lower().startswith(_URL_PREFIXES)
                                for u in CONFIG.get("rtsp_urls", {}).values())
                if FILE_EXIT_WHEN_DONE and all_files and not other_files_running:
                    print("[INFO] All video files finished - closing the application "
                          "(\"file_exit_when_done\"; same as Ctrl+C).")
                    os.kill(os.getpid(), signal.SIGINT)
                else:
                    print("[INFO] Video file finished. The application keeps running "
                          "(press Ctrl+C to stop it).")
            elif is_file_source:
                print("[INFO] Video file playback stopped (the application is not restarted for video files; "
                      "press Ctrl+C to stop it).")
            elif self.on_done_callback:
                self.on_done_callback(self.camera_id)