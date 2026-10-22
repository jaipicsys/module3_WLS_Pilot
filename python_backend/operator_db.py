from datetime import datetime

from db import get_db_connection

COLUMNS = [
    "line_id", "product_name", "shift_id", "shift_timings",
    "break_name", "break_timings", "operation", "station_name",
    "cam_id", "start_time", "status", "reasons", "operator_id", "plant",
]


def _ts(moment):
    """datetime (or 'YYYY-MM-DD HH:MM:SS' string) -> 'YYYY-MM-DD HH:MM:SS'."""
    if isinstance(moment, str):
        return moment
    return moment.isoformat(sep=" ", timespec="seconds")


def open_segment(row):
    """Insert a new status row with empty end_time. Returns its id."""
    conn = get_db_connection()
    try:
        cur = conn.execute(
            f"INSERT INTO operator_status ({', '.join(COLUMNS)}) "
            f"VALUES ({', '.join('?' for _ in COLUMNS)})",
            [row.get(c) for c in COLUMNS],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def close_segment(segment_id, end_time, duration_seconds):
    """Fill end_time and durations on the open row."""
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE operator_status SET end_time = ?, durations = ? WHERE id = ?",
            (end_time, round(duration_seconds, 2), segment_id),
        )
        conn.commit()
    finally:
        conn.close()


def close_open_segments(cam_id, closed_at=None):
    """
    Close every still-open row of one camera at `closed_at` (default: now).
    Call it with the time of the LAST PROCESSED FRAME when the stream ends or the
    camera disconnects. Returns how many rows were closed.
    """
    closed_at = _ts(closed_at or datetime.now())
    conn = get_db_connection()
    try:
        cur = conn.execute(
            """
            UPDATE operator_status
            SET end_time  = MAX(?, start_time),
                durations = ROUND((julianday(MAX(?, start_time)) - julianday(start_time)) * 86400, 2)
            WHERE cam_id = ? AND end_time IS NULL
            """,
            (closed_at, closed_at, cam_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def close_stale_segments():
    """
    Run once at startup. Rows left open by a crash or restart are closed at the
    last time that camera wrote anything (its latest end_time/start_time), not at
    the current time, so the gap while the backend was down is not counted.
    """
    conn = get_db_connection()
    try:
        total = 0
        cams = conn.execute(
            """
            SELECT cam_id, MAX(COALESCE(end_time, start_time)) AS last_seen
            FROM operator_status
            GROUP BY cam_id
            HAVING SUM(end_time IS NULL) > 0
            """
        ).fetchall()

        for cam in cams:
            cur = conn.execute(
                """
                UPDATE operator_status
                SET end_time  = ?,
                    durations = ROUND((julianday(?) - julianday(start_time)) * 86400, 2)
                WHERE cam_id IS ? AND end_time IS NULL
                """,
                (cam["last_seen"], cam["last_seen"], cam["cam_id"]),
            )
            total += cur.rowcount

        conn.commit()
        if total:
            print(f"[DB] Closed {total} stale operator_status row(s).")
    finally:
        conn.close()