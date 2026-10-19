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


def add_count(info, n, now=None):
    """Add n units to today's row for this shift / station (creates it if missing)."""
    now = now or datetime.now()
    stamp = now.isoformat(sep=" ", timespec="seconds")
    day = shift_date(info.get("shift_timings"), now)

    conn = get_db_connection()
    try:
        cur = conn.execute(
            """
            UPDATE unit_count
            SET unit_count = COALESCE(unit_count, 0) + ?, updated_at = ?
            WHERE count_date = ? AND line_id = ? AND shift_id IS ?
              AND station_name = ? AND cam_id = ?
            """,
            (n, stamp, day, info["line_id"], info["shift_id"],
             info["station_name"], info["cam_id"]),
        )
        if cur.rowcount == 0:
            conn.execute(
                """
                INSERT INTO unit_count
                (line_id, product_name, shift_id, shift_timings, operation,
                 station_name, cam_id, unit_count, plant, count_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (info["line_id"], info["product_name"], info["shift_id"],
                 info["shift_timings"], info["operation"], info["station_name"],
                 info["cam_id"], n, info["plant"], day, stamp),
            )
        conn.commit()
    finally:
        conn.close()