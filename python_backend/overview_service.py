"""
KPI cards for the Overview page, built from whatever is in data.db
(all dates, no filters). Read-only: nothing here creates tables or writes rows.

  Total Output          -> total_output
  Output / Hour         -> output_per_hour
  Productive Time       -> productive_time
  Idle / Waiting Time   -> idle_time

Productive and idle time are the sum of every operator's time.
"""

import sqlite3
from datetime import datetime

from db import get_db_connection

# Optional per-unit table (one row per finished unit). If it does not exist the
# API simply uses unit_count. Set these to your table, or leave them: if the
# table below is missing, any extra table with a time column is picked up.
UNIT_EVENTS_TABLE = "unit_events"
UNIT_EVENTS_TIME_COLUMN = "event_time"

KNOWN_TABLES = {"operator_status", "unit_count", "cycle_time", "sqlite_sequence", "users"}
TIME_COLUMN_CANDIDATES = (
    "event_time", "timestamp", "counted_at", "count_time", "unit_time",
    "created_at", "time", "ts",
)

# An open status row counts up to "now" only if the cameras wrote something
# this recently; otherwise it stops at the last time anything was seen.
LIVE_GRACE_SECONDS = 120

PRODUCTIVE_STATUSES = ("active_work",)
IDLE_STATUSES = ("idle",)
AWAY_STATUSES = ("away",)


def _parse(value):
    return datetime.fromisoformat(value) if value else None


def fmt_duration(seconds):
    """3725 -> '1h 2m', 123 -> '2m 3s', 42 -> '42s'."""
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def fmt_hours_minutes(seconds):
    """Hours and minutes only, rounded to the nearest minute: 1427 -> '0h 24m'."""
    minutes = int(round(seconds / 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def unit_events_source(conn):
    """
    Finds the per-unit table. Returns (table, time_column, product_column or None),
    or None when there is no such table (callers then use unit_count).
    """
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    ordered = [t for t in tables if t == UNIT_EVENTS_TABLE] + [
        t for t in tables if t != UNIT_EVENTS_TABLE and t not in KNOWN_TABLES
    ]

    for table in ordered:
        columns = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}
        candidates = (UNIT_EVENTS_TIME_COLUMN,) + TIME_COLUMN_CANDIDATES
        time_col = next((c for c in candidates if c in columns), None)
        if time_col:
            return table, time_col, ("product_name" if "product_name" in columns else None)
    return None


# ---------------- operator_status -> productive / idle ----------------

def status_segments(conn, now):
    """
    Every operator_status row with its length in seconds.
    Returns (segments, live). A row that is still open counts up to "now" only
    if the cameras wrote something recently; otherwise it stops at the last
    time anything was seen.
    """
    rows = conn.execute(
        "SELECT operator_id, status, reasons, start_time, end_time, durations "
        "FROM operator_status"
    ).fetchall()
    if not rows:
        return [], False

    last_seen = max(_parse(r["end_time"] or r["start_time"]) for r in rows)
    live = (now - last_seen).total_seconds() <= LIVE_GRACE_SECONDS
    open_end = now if live else min(now, last_seen)

    segments = []
    for row in rows:
        start = _parse(row["start_time"])
        end = _parse(row["end_time"]) if row["end_time"] else open_end
        if end <= start:
            continue

        if row["end_time"] and row["durations"] is not None:
            seconds = float(row["durations"])
        else:
            seconds = (end - start).total_seconds()

        segments.append({
            "operator_id": row["operator_id"] or "Unknown",
            "status": row["status"],
            "reason": row["reasons"],
            "start": start,
            "end": end,
            "seconds": seconds,
        })
    return segments, live


def _status_time(conn, now):
    segments, live = status_segments(conn, now)
    if not segments:
        return None

    days = {}  # date -> productive / idle / away seconds, first/last time
    for seg in segments:
        day = days.setdefault(
            seg["start"].date(),
            {"productive": 0.0, "idle": 0.0, "away": 0.0, "span": [seg["start"], seg["end"]]},
        )
        day["span"][0] = min(day["span"][0], seg["start"])
        day["span"][1] = max(day["span"][1], seg["end"])

        if seg["status"] in PRODUCTIVE_STATUSES:
            day["productive"] += seg["seconds"]
        elif seg["status"] in IDLE_STATUSES:
            day["idle"] += seg["seconds"]
        elif seg["status"] in AWAY_STATUSES:
            day["away"] += seg["seconds"]

    return {
        "productive": sum(d["productive"] for d in days.values()),
        "idle": sum(d["idle"] for d in days.values()),
        "away": sum(d["away"] for d in days.values()),
        "day_spans": {d: day["span"] for d, day in days.items()},
        "live": live,
    }


# ---------------- output ----------------

def _events_output(conn):
    """Per-unit rows if that table exists and has data, else None."""
    source = unit_events_source(conn)
    if not source:
        return None
    table, col, _ = source
    try:
        total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        if not total:
            return None
        day_rows = conn.execute(
            f'SELECT date("{col}") AS d, MIN("{col}") AS first, MAX("{col}") AS last '
            f'FROM "{table}" GROUP BY d'
        ).fetchall()
    except sqlite3.OperationalError:
        return None

    return {
        "total": total,
        "day_spans": {
            datetime.strptime(r["d"], "%Y-%m-%d").date(): [_parse(r["first"]), _parse(r["last"])]
            for r in day_rows
        },
    }


def _count_output(conn):
    """unit_count: total units, and when they were counted (updated_at)."""
    total, rows = conn.execute(
        "SELECT COALESCE(SUM(unit_count), 0), COUNT(*) FROM unit_count"
    ).fetchone()
    if not rows:
        return None

    day_spans = {}
    try:
        for r in conn.execute(
            "SELECT date(updated_at) AS d, MIN(updated_at) AS first, MAX(updated_at) AS last "
            "FROM unit_count WHERE updated_at IS NOT NULL GROUP BY d"
        ).fetchall():
            day_spans[datetime.strptime(r["d"], "%Y-%m-%d").date()] = [
                _parse(r["first"]), _parse(r["last"])
            ]
    except sqlite3.OperationalError:
        pass

    return {"total": int(total), "day_spans": day_spans}


# ---------------- public ----------------

def get_kpi_cards():
    now = datetime.now().replace(microsecond=0)

    conn = get_db_connection()
    try:
        status = _status_time(conn, now)
        output = _events_output(conn) or _count_output(conn)
    finally:
        conn.close()

    # Output / hour: total output over the time units were being produced
    # (first to last unit, per day so overnight gaps don't count). If there is
    # no per-unit time (just one count), use the operators' activity instead.
    def span_seconds(spans):
        return sum((last - first).total_seconds() for first, last in spans.values())

    observed = span_seconds(output["day_spans"]) if output else 0
    if observed < 60:
        spans = {}
        for source in (status, output):
            for day, (first, last) in (source["day_spans"] if source else {}).items():
                span = spans.setdefault(day, [first, last])
                span[0] = min(span[0], first)
                span[1] = max(span[1], last)
        observed = span_seconds(spans)

    total_output = output["total"] if output else None
    output_per_hour = None
    if total_output is not None and observed >= 60:
        output_per_hour = round(total_output / (observed / 3600), 1)

    productive_time = idle_time = None
    if status:
        tracked = status["productive"] + status["idle"] + status["away"]

        def card(seconds):
            return {
                "seconds": round(seconds, 1),
                "display": fmt_hours_minutes(seconds),
                "pct_of_available": round(seconds / tracked * 100, 1) if tracked else 0,
            }

        productive_time = card(status["productive"])
        idle_time = card(status["idle"])

    # null = no data, the UI shows a dash.
    return {
        "total_output": None if total_output is None else {"value": total_output, "change_pct": None},
        "output_per_hour": None if output_per_hour is None else {"value": output_per_hour, "change_pct": None},
        "productive_time": productive_time,
        "idle_time": idle_time,
    }