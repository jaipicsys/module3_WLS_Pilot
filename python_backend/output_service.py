"""
Output Trend (5-minute bars) and Output by Product. Read-only, no filters.

Both read the per-unit table when there is one (see unit_events_source in
overview_service.py) and fall back to unit_count when there is not.
"""

from datetime import datetime, timedelta

from db import get_db_connection
from overview_service import unit_events_source

BUCKET_MINUTES = 5

# Keep drawing empty bars up to "now" only while units are still arriving
# (last unit newer than this); otherwise the chart stops at the last unit.
EXTEND_TO_NOW_WITHIN = timedelta(minutes=10)

# Target line on the trend chart. There is no target stored anywhere yet, so
# this is off (null). Set e.g. 120 to draw 120 units/hour = 10 units per bucket.
TARGET_PER_HOUR = None

# The product chart always shows this many rows. Products with no data yet are
# filled in with 0-count placeholders so the chart keeps its shape.
PRODUCT_ROWS = 5
PLACEHOLDER_PRODUCTS = ["Towel – Premium", "Hand Towel", "Bath Towel", "Others"]


def _label(moment):
    hour = moment.hour % 12 or 12
    return f"{hour}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"


def _bucket(moment):
    return moment.replace(
        minute=moment.minute - moment.minute % BUCKET_MINUTES, second=0, microsecond=0
    )


# ---------------- Output Trend ----------------

def _describe_tables(conn):
    """{table: {rows, columns}} so an empty chart can say what it found."""
    info = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
    ).fetchall():
        columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")').fetchall()]
        rows = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        info[name] = {"rows": rows, "columns": columns}
    return info


def get_output_trend():
    """Units finished per 5 minutes, for the most recent day that has data."""
    empty = {"interval_minutes": BUCKET_MINUTES, "date": None, "series": []}

    conn = get_db_connection()
    try:
        # One row per unit: a separate per-unit table if there is one, otherwise
        # unit_count itself (each row = units counted, stamped with updated_at).
        source = unit_events_source(conn)
        if source:
            table, col, _ = source
            weight = "1"
        else:
            table, col, weight = "unit_count", "updated_at", "COALESCE(unit_count, 1)"

        day = conn.execute(f'SELECT MAX(date("{col}")) FROM "{table}"').fetchone()[0]
        if not day:
            return {
                **empty,
                "reason": f'No rows with a valid time in "{table}"."{col}".',
                "tables": _describe_tables(conn),
            }
        rows = conn.execute(
            f'SELECT "{col}", {weight} FROM "{table}" WHERE date("{col}") = ?', (day,)
        ).fetchall()
    finally:
        conn.close()

    counts = {}
    last_unit = None
    for row in rows:
        moment = datetime.fromisoformat(row[0])
        key = _bucket(moment)
        counts[key] = counts.get(key, 0) + int(row[1] or 0)
        last_unit = moment if last_unit is None else max(last_unit, moment)

    first, last = min(counts), max(counts)
    now = datetime.now()
    if now - last_unit <= EXTEND_TO_NOW_WITHIN:
        last = max(last, _bucket(now))  # live: keep the chart moving

    target = (
        round(TARGET_PER_HOUR * BUCKET_MINUTES / 60, 1) if TARGET_PER_HOUR else None
    )

    series = []
    step = timedelta(minutes=BUCKET_MINUTES)
    moment = first
    while moment <= last:
        series.append({
            "time": moment.strftime("%Y-%m-%d %H:%M:%S"),
            "label": _label(moment),
            "output": counts.get(moment, 0),
            "target": target,
        })
        moment += step

    return {"interval_minutes": BUCKET_MINUTES, "date": day, "series": series}


# ---------------- Output by Product ----------------

def get_output_by_product():
    """Total units per product, biggest first, padded to PRODUCT_ROWS rows."""
    conn = get_db_connection()
    try:
        counts = []
        source = unit_events_source(conn)
        if source and source[2]:
            table, _, product_col = source
            counts = conn.execute(
                f'SELECT COALESCE("{product_col}", \'Unknown\') AS name, COUNT(*) AS value '
                f'FROM "{table}" GROUP BY name'
            ).fetchall()

        if not counts:
            counts = conn.execute(
                "SELECT COALESCE(product_name, 'Unknown') AS name, "
                "COALESCE(SUM(unit_count), 0) AS value "
                "FROM unit_count GROUP BY name"
            ).fetchall()
    finally:
        conn.close()

    products = sorted(
        ({"name": r["name"], "value": int(r["value"]), "placeholder": False} for r in counts),
        key=lambda p: -p["value"],
    )

    present = {p["name"] for p in products}
    for name in PLACEHOLDER_PRODUCTS:
        if len(products) >= PRODUCT_ROWS:
            break
        if name not in present:
            products.append({"name": name, "value": 0, "placeholder": True})

    return {"products": products}