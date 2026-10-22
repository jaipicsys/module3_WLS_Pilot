import base64
from flask import Blueprint, Response, jsonify, request, stream_with_context
from db import MODES, RECORDED_DB_FILE, get_db_connection, recorded_available
from frame_hub import hub
import operators_service
import output_service
import overview_service

api_bp = Blueprint("api", __name__)

def _with_mode(service_function):
    """
    Runs a dashboard service for ?mode=live (default) or ?mode=recorded.
    live     -> data.db, what the cameras are writing now
    recorded -> the saved run named in db.py (RECORDED_DB_FILE), read-only
    """
    mode = request.args.get("mode", "live").lower()

    if mode not in MODES:
        return jsonify({"error": f"mode must be one of {list(MODES)}"}), 400

    try:
        return jsonify(service_function(mode)), 200
    except FileNotFoundError:
        return jsonify({"error": f"Recorded data is not available ({RECORDED_DB_FILE} not found)."}), 404

@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@api_bp.route("/modes", methods=["GET"])
def modes():
    """Which modes can be used, and the time range the recorded data covers."""
    recorded = {"id": "recorded", "name": RECORDED_DB_FILE, "available": recorded_available()}

    if recorded["available"]:
        conn = get_db_connection("recorded")
        try:
            first, last = conn.execute(
                "SELECT MIN(start_time), MAX(COALESCE(end_time, start_time)) FROM operator_status"
            ).fetchone()
            recorded["from"], recorded["to"] = first, last
        finally:
            conn.close()

    return jsonify({"modes": [{"id": "live", "available": True}, recorded]}), 200


# ---------------- Dashboard (all accept ?mode=live|recorded) ----------------

@api_bp.route("/kpi-cards", methods=["GET"])
def kpi_cards():
    """The four Overview KPI cards."""
    return _with_mode(overview_service.get_kpi_cards)

@api_bp.route("/output-trend", methods=["GET"])
def output_trend():
    """Output Trend chart: units per 5 minutes for the latest day with data."""
    return _with_mode(output_service.get_output_trend)

@api_bp.route("/output-by-product", methods=["GET"])
def output_by_product():
    """Output by Product chart: units per product (placeholders fill to 5 rows)."""
    return _with_mode(output_service.get_output_by_product)

@api_bp.route("/top-operators", methods=["GET"])
def top_operators():
    """Top Operators table: active / idle / away time and utilization."""
    return _with_mode(operators_service.get_top_operators)

@api_bp.route("/loss-breakdown", methods=["GET"])
def loss_breakdown():
    """Loss Breakdown chart: idle and away time grouped by reason."""
    return _with_mode(operators_service.get_loss_breakdown)

# ---------------- Live camera feed (always live) ----------------

@api_bp.route("/cameras", methods=["GET"])
def cameras():
    """Configured cameras and whether each is delivering frames: [{id, online}]."""
    return jsonify({"cameras": hub.cameras()}), 200

@api_bp.route("/camera/<cam_id>/stream", methods=["GET"])
def camera_stream(cam_id):
    """Live MJPEG feed. Use it directly as <img src=".../api/camera/<id>/stream">."""
    if not hub.known(cam_id):
        return jsonify({"error": f"Unknown camera '{cam_id}'"}), 404
    return Response(
        stream_with_context(hub.stream(cam_id)),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )

@api_bp.route("/camera/<cam_id>/snapshot", methods=["GET"])
def camera_snapshot(cam_id):
    """One JPEG of the camera right now."""
    if not hub.known(cam_id):
        return jsonify({"error": f"Unknown camera '{cam_id}'"}), 404
    jpeg = hub.snapshot(cam_id)
    if jpeg is None:
        return jsonify({"error": "No frame available yet"}), 503
    return Response(jpeg, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

@api_bp.route("/camera_frame/<cam_id>", methods=["GET"])
def camera_frame(cam_id):
    """Same snapshot as base64 JSON, for the existing fetchCameraFrame() in api.js."""
    if not hub.known(cam_id):
        return jsonify({"error": f"Unknown camera '{cam_id}'"}), 404
    jpeg = hub.snapshot(cam_id)
    if jpeg is None:
        return jsonify({"error": "No frame available yet"}), 503
    return jsonify({"image": base64.b64encode(jpeg).decode("ascii")}), 200