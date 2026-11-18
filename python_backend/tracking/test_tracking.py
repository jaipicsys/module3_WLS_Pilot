"""
Test person tracking + OSNet ReID on a camera, RTSP url or video file (no app.py needed).

  python tracking/test_tracking.py --source cam1                  # camera name from config.json
  python tracking/test_tracking.py --source /path/video.mp4 --show
  python tracking/test_tracking.py --source video.mp4 --no-reid   # A/B: BoT-SORT ids only

Saves tracking/output/<name>_reid_ON|OFF.mp4 and prints a summary.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000")

import cv2

from config_utils import CONFIG
from tracking.tracking_logic import TrackingLogic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="camera name (e.g. cam1), rtsp url or video file")
    ap.add_argument("--no-reid", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()

    src = CONFIG.get("rtsp_urls", {}).get(args.source, args.source)
    name = args.source if args.source in CONFIG.get("rtsp_urls", {}) else Path(args.source).stem

    logic = TrackingLogic(name, with_reid=not args.no_reid)
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open source: {src}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if 1 < fps < 120 else 10

    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{name}_reid_{'OFF' if args.no_reid else 'ON'}.mp4"
    writer, n = None, 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            n += 1
            vis = logic.process(frame)
            if writer is None:
                h, w = vis.shape[:2]
                writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            writer.write(vis)
            if args.show:
                cv2.imshow("tracking", cv2.resize(vis, None, fx=0.5, fy=0.5))
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break
            if args.max_frames and n >= args.max_frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()

    print("\n==== TRACKING SUMMARY ====")
    for k, v in logic.tracker.summary().items():
        print(f"  {k:<14} {v}")
    print(f"  video saved    {out_path}")


if __name__ == "__main__":
    main()