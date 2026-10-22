from flask import Blueprint, jsonify

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