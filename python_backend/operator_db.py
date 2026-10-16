from datetime import datetime

from db import get_db_connection

COLUMNS = [
    "line_id", "product_name", "shift_id", "shift_timings",
    "break_name", "break_timings", "operation", "station_name",
    "cam_id", "start_time", "status", "reasons", "operator_id", "plant",
]


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


def close_stale_segments():
    """
    Run once at startup. Rows left open by a crash or restart
    get closed at the current time, so reports don't see NULL end_time.
    """
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    conn = get_db_connection()
    try:
        cur = conn.execute(
            """
            UPDATE operator_status
            SET end_time = ?,
                durations = ROUND((julianday(?) - julianday(start_time)) * 86400, 2)
            WHERE end_time IS NULL
            """,
            (now, now),
        )
        conn.commit()
        if cur.rowcount:
            print(f"[DB] Closed {cur.rowcount} stale operator_status row(s).")
    finally:
        conn.close()