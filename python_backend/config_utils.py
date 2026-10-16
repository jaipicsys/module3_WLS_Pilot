import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
    CONFIG = json.load(f)


def resolve_model_path(filename):
    path = os.path.join(BASE_DIR, CONFIG.get("models_dir", "models"), filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model not found: {path}")
    return path


def find_station_for_camera(camera_id):
    """Returns (line_id, line, station_id, station) or None."""
    for line_id, line in CONFIG.get("lines", {}).items():
        for station_id, station in line.get("stations", {}).items():
            if station.get("camera") == camera_id:
                return line_id, line, station_id, station
    return None


def _parse_range(text):
    start, end = [
        datetime.strptime(p.strip(), "%H:%M").time()
        for p in text.split("-")
    ]
    return start, end


def _in_range(t, start, end):
    if start <= end:
        return start <= t < end
    return t >= start or t < end  # crosses midnight


def get_shift_and_break(line, now=None):
    """Returns (shift_dict_or_None, break_dict_or_None) for the given time."""
    now = now or datetime.now()
    t = now.time()

    for shift in line.get("shifts", []):
        start, end = _parse_range(shift["timings"])
        if _in_range(t, start, end):
            for brk in shift.get("breaks", []):
                b_start, b_end = _parse_range(brk["timings"])
                if _in_range(t, b_start, b_end):
                    return shift, brk
            return shift, None

    return None, None