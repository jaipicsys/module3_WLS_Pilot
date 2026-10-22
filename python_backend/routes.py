import base64
 
from flask import Blueprint, Response, jsonify, stream_with_context
 
from frame_hub import hub
import operators_service
import output_service
import overview_service

api_bp = Blueprint("api", __name__)


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@api_bp.route("/kpi-cards", methods=["GET"])
def kpi_cards():
    """The four Overview KPI cards, from all data in data.db."""
    return jsonify(overview_service.get_kpi_cards()), 200


@api_bp.route("/output-trend", methods=["GET"])
def output_trend():
    """Output Trend chart: units per 5 minutes for the latest day with data."""
    return jsonify(output_service.get_output_trend()), 200


@api_bp.route("/output-by-product", methods=["GET"])
def output_by_product():
    """Output by Product chart: units per product (placeholders fill to 5 rows)."""
    return jsonify(output_service.get_output_by_product()), 200


@api_bp.route("/top-operators", methods=["GET"])
def top_operators():
    """Top Operators table: active / idle / away time and utilization."""
    return jsonify(operators_service.get_top_operators()), 200


@api_bp.route("/loss-breakdown", methods=["GET"])
def loss_breakdown():
    """Loss Breakdown chart: idle and away time grouped by reason."""
    return jsonify(operators_service.get_loss_breakdown()), 200

# ---------------- Live camera feed ----------------
 
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
 