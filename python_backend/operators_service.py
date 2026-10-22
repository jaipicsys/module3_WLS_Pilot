"""
Top Operators table and Loss Breakdown chart, from operator_status
(all dates, no filters, read-only).
"""

from datetime import datetime

from db import get_db_connection
from overview_service import (
    AWAY_STATUSES,
    IDLE_STATUSES,
    PRODUCTIVE_STATUSES,
    fmt_duration,
    status_segments,
)

TOP_OPERATORS = None  # rows in the table: None = every operator, or set a number like 5
LOSS_ROWS = 5       # rows in the chart; extra reasons are grouped into "Others"


def _load_segments(mode="live"):
    conn = get_db_connection(mode)
    try:
        segments, _ = status_segments(conn, datetime.now().replace(microsecond=0))
    finally:
        conn.close()
    return segments


# ---------------- Top Operators ----------------

def get_top_operators(mode="live"):
    """Operators ranked by active time. Utilization = active / (active + idle + away)."""
    totals = {}
    for seg in _load_segments(mode):
        op = totals.setdefault(
            seg["operator_id"], {"active": 0.0, "idle": 0.0, "away": 0.0}
        )
        if seg["status"] in PRODUCTIVE_STATUSES:
            op["active"] += seg["seconds"]
        elif seg["status"] in IDLE_STATUSES:
            op["idle"] += seg["seconds"]
        elif seg["status"] in AWAY_STATUSES:
            op["away"] += seg["seconds"]

    ranked = sorted(totals.items(), key=lambda item: -item[1]["active"])[:TOP_OPERATORS]

    operators = []
    for rank, (operator_id, t) in enumerate(ranked, start=1):
        tracked = t["active"] + t["idle"] + t["away"]
        operators.append({
            "rank": rank,
            "operator_id": operator_id,
            "active_seconds": round(t["active"], 1),
            "active_display": fmt_duration(t["active"]),
            "idle_seconds": round(t["idle"], 1),
            "idle_display": fmt_duration(t["idle"]),
            "away_seconds": round(t["away"], 1),
            "away_display": fmt_duration(t["away"]),
            "utilization_pct": round(t["active"] / tracked * 100, 1) if tracked else 0,
        })

    return {"operators": operators}


# ---------------- Loss Breakdown ----------------

def get_loss_breakdown(mode="live"):
    """Idle and away time grouped by reason, biggest first."""
    by_reason = {}
    for seg in _load_segments(mode):
        if seg["status"] in IDLE_STATUSES:
            kind = "idle"
        elif seg["status"] in AWAY_STATUSES:
            kind = "away"
        else:
            continue

        label = seg["reason"] or "Unspecified"
        row = by_reason.setdefault((label, kind), 0.0)
        by_reason[(label, kind)] = row + seg["seconds"]

    rows = sorted(
        ({"label": label, "type": kind, "seconds": seconds}
         for (label, kind), seconds in by_reason.items()),
        key=lambda r: -r["seconds"],
    )

    if len(rows) > LOSS_ROWS:
        rest = rows[LOSS_ROWS - 1:]
        rows = rows[:LOSS_ROWS - 1] + [
            {"label": "Others", "type": "mixed", "seconds": sum(r["seconds"] for r in rest)}
        ]

    total = sum(r["seconds"] for r in rows)
    items = [
        {
            "label": r["label"],
            "type": r["type"],
            "seconds": round(r["seconds"], 1),
            "display": fmt_duration(r["seconds"]),
            "pct": round(r["seconds"] / total * 100, 1) if total else 0,
        }
        for r in rows
    ]

    return {
        "total_seconds": round(total, 1),
        "total_display": fmt_duration(total),
        "items": items,
    }