"""Shared, bounded-batch YOLO inference for multiple camera workers.

Each camera submits one frame and waits for its own Results object. When two
camera frames arrive within batch_wait_ms, one YOLO.predict call processes both.
If a camera is late/disconnected, the available frame is processed alone so the
other camera never stalls indefinitely. Tracking state is deliberately NOT kept
here; each PersonTracker owns its own BoT-SORT and OSNet/Re-ID state.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from ultralytics import YOLO


@dataclass
class _Request:
    camera_id: str
    frame: Any
    event: threading.Event
    result: Any = None
    error: BaseException | None = None


class SharedBatchDetector:
    def __init__(self, weights, device, classes, conf, imgsz, batch_size=2, batch_wait_ms=30):
        self.weights = str(weights)
        self.device = device
        self.classes = None if classes is None else list(classes)
        self.conf = float(conf)
        self.imgsz = imgsz
        self.batch_size = max(1, int(batch_size))
        self.batch_wait_s = max(0.0, float(batch_wait_ms) / 1000.0)

        self.model = YOLO(self.weights)
        self._condition = threading.Condition()
        self._pending: list[_Request] = []
        self._stopping = False
        self._batch_count = 0
        self._single_count = 0
        self._worker = threading.Thread(
            target=self._run, name="shared-yolo-batch-inference", daemon=True
        )
        self._worker.start()
        print(
            f"[BATCH] Shared YOLO loaded: {self.weights}; device={self.device}; "
            f"max_batch={self.batch_size}; wait={self.batch_wait_s * 1000:.0f}ms"
        )

    def set_classes(self, classes):
        classes = [int(c) for c in classes]
        with self._condition:
            if self.classes is None:
                self.classes = classes
            elif self.classes != classes:
                raise ValueError(
                    "Cameras sharing one YOLO detector must use identical person_classes"
                )

    def infer(self, camera_id, frame):
        request = _Request(str(camera_id), frame, threading.Event())
        with self._condition:
            if self._stopping:
                raise RuntimeError("Shared YOLO batch detector is stopping")
            self._pending.append(request)
            self._condition.notify_all()

        # The batch worker always resolves every request, including on inference errors.
        request.event.wait()
        if request.error is not None:
            raise RuntimeError(f"YOLO inference failed for {camera_id}") from request.error
        return request.result

    def _run(self):
        while True:
            with self._condition:
                while not self._pending and not self._stopping:
                    self._condition.wait()
                if self._stopping and not self._pending:
                    return

                deadline = time.monotonic() + self.batch_wait_s
                while len(self._pending) < self.batch_size and not self._stopping:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._condition.wait(remaining)

                batch = self._pending[: self.batch_size]
                del self._pending[: len(batch)]

            try:
                frames = [item.frame for item in batch]
                # Ultralytics accepts a list of NumPy frames and returns one Results
                # object per input frame. This is detection-only; BoT-SORT is per camera.
                results = self.model.predict(
                    source=frames,
                    classes=self.classes,
                    conf=self.conf,
                    imgsz=self.imgsz,
                    device=self.device,
                    half=False,
                    verbose=False,
                    agnostic_nms=len(self.classes) > 1,
                    stream=False,
                )
                if len(results) != len(batch):
                    raise RuntimeError(
                        f"YOLO returned {len(results)} results for {len(batch)} frames"
                    )
                if len(batch) == self.batch_size:
                    self._batch_count += 1
                else:
                    self._single_count += 1
                if (self._batch_count + self._single_count) % 100 == 0:
                    print(
                        f"[BATCH] YOLO calls: paired={self._batch_count}, "
                        f"single={self._single_count}"
                    )
                for item, result in zip(batch, results):
                    item.result = result
            except BaseException as exc:  # deliver failure to every waiting camera
                for item in batch:
                    item.error = exc
            finally:
                for item in batch:
                    item.event.set()


_DETECTORS: dict[tuple, SharedBatchDetector] = {}
_DETECTORS_LOCK = threading.Lock()


def get_shared_detector(weights, device, classes, conf, imgsz, batch_size=2, batch_wait_ms=30):
    """Return one detector for identical model/inference settings across cameras."""
    key = (
        str(weights), str(device), None if classes is None else tuple(int(c) for c in classes), float(conf),
        str(imgsz), int(batch_size), float(batch_wait_ms),
    )
    with _DETECTORS_LOCK:
        detector = _DETECTORS.get(key)
        if detector is None:
            detector = SharedBatchDetector(
                weights, device, classes, conf, imgsz, batch_size, batch_wait_ms
            )
            _DETECTORS[key] = detector
        return detector