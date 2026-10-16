import json
import os

from flask import Flask
from flask_cors import CORS

import operator_db
from camera_manager import CameraManager
from db import init_all_databases
from routes import api_bp


# Load configuration relative to this file.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as file:
    CONFIG = json.load(file)

FLASK_HOST = CONFIG.get("host", "0.0.0.0")
FLASK_PORT = CONFIG.get("flask_port", 5000)
CAMERA_CONFIG = CONFIG.get("rtsp_urls", {})
ENABLE_DISPLAY = CONFIG.get("enable_display", False)
DISPLAY_SCALE = CONFIG.get("display_scale", 0.6)


app = Flask(__name__)

CORS(
    app,
    supports_credentials=True,
    origins=["*"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)

app.register_blueprint(api_bp, url_prefix="/api")


if __name__ == "__main__":
    # Initialize all required database tables.
    init_all_databases()

    # Close rows left open by a previous crash or restart.
    operator_db.close_stale_segments()

    # Start configured cameras in background threads.
    manager = CameraManager(
        CAMERA_CONFIG,
        enable_display=ENABLE_DISPLAY,
        display_scale=DISPLAY_SCALE,
    )
    manager.start_all()

    # Start Flask without the development reloader.
    try:
        app.run(
            host=FLASK_HOST,
            port=FLASK_PORT,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        print("\n[INFO] Received keyboard interrupt.")