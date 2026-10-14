import json
import os

from flask import Flask
from flask_cors import CORS

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

    # Start configured cameras in background threads.
    manager = CameraManager(CAMERA_CONFIG)
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
