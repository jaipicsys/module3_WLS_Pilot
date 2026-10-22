from datetime import datetime, timedelta

from db import get_db_connection


def shift_date(shift_timings, now=None):
    """Date a shift belongs to. Shift 3 (22:00-06:00) after midnight is yesterday's."""
    now = now or datetime.now()
    if not shift_timings:
        return now.date().isoformat()

    start, end = [p.strip() for p in shift_timings.split("-")]
    if start > end and now.strftime("%H:%M") < end:      # crosses midnight
        return (now - timedelta(days=1)).date().isoformat()
    return now.date().isoformat()


def add_count(info, n=1, now=None):
    """Insert n rows, one per unit produced (each row has unit_count = 1)."""
    now = now or datetime.now()
    stamp = now.isoformat(sep=" ", timespec="seconds")
    day = shift_date(info.get("shift_timings"), now)

    row = (
        info["line_id"], info["product_name"], info["shift_id"],
        info["shift_timings"], info.get("break_name"), info.get("break_timings"),
        info["operation"], info["station_name"], info["cam_id"],
        1, info["plant"], day, stamp,
    )

    conn = get_db_connection()
    try:
        conn.executemany(
            """
            INSERT INTO unit_count
            (line_id, product_name, shift_id, shift_timings, break_name,
             break_timings, operation, station_name, cam_id, unit_count,
             plant, count_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [row] * max(1, int(n)),
        )
        conn.commit()
    finally:
        conn.close()