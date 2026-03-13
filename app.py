import json
import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from services.model import ModelService
from services.mqtt_client import MqttClient
from services.recommendation import RecommendationEngine
from services.storage import Storage
from services.weather import WeatherProvider


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    storage = Storage(db_path=os.getenv("DB_PATH", "data/app.db"))
    storage.init_db()

    model_service = ModelService(
        model_path=os.getenv("MODEL_PATH", "output/best_catboost_model.cbm"),
        feature_order=os.getenv("MODEL_FEATURES", ""),
    )
    recommender = RecommendationEngine()
    weather = WeatherProvider()

    mqtt_enabled = os.getenv("MQTT_ENABLE", "true").lower() == "true"
    if mqtt_enabled:
        mqtt_client = MqttClient(
            host=os.getenv("MQTT_HOST", "localhost"),
            port=int(os.getenv("MQTT_PORT", "1883")),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
            topic=os.getenv("MQTT_TOPIC", "sensors/#"),
            storage=storage,
        )

        def mqtt_thread():
            mqtt_client.run_forever()

        threading.Thread(target=mqtt_thread, daemon=True).start()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})

    @app.route("/api/latest")
    def latest():
        admin_code = request.args.get("admin_code", "")
        limit = int(request.args.get("limit", "200"))
        data = storage.get_latest_readings(admin_code=admin_code, limit=limit)
        return jsonify({"data": data})

    @app.route("/api/grid")
    def grid():
        try:
            bbox = request.args.get("bbox", "")
            resolution_km = float(request.args.get("resolution_km", "1"))
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox requires 4 numbers")
            min_lon, min_lat, max_lon, max_lat = parts
        except Exception:
            return jsonify({"error": "Invalid bbox. Use min_lon,min_lat,max_lon,max_lat"}), 400

        grid = WeatherProvider.generate_grid(min_lon, min_lat, max_lon, max_lat, resolution_km)
        return jsonify({"grid": grid})

    @app.route("/api/weather")
    def weather_api():
        try:
            lat = float(request.args.get("lat"))
            lon = float(request.args.get("lon"))
        except Exception:
            return jsonify({"error": "lat/lon required"}), 400
        data = weather.get_realtime(lat=lat, lon=lon)
        return jsonify({"data": data})

    @app.route("/api/predict", methods=["POST"])
    def predict():
        payload = request.get_json(force=True, silent=True) or {}
        features = payload.get("features", {})
        if not isinstance(features, dict):
            return jsonify({"error": "features must be an object"}), 400

        try:
            prediction = model_service.predict(features)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        suggestion = recommender.suggest(features, prediction)
        storage.insert_prediction(features=features, prediction=prediction, suggestion=suggestion)

        return jsonify({"prediction": prediction, "suggestion": suggestion})

    @app.route("/api/ingest", methods=["POST"])
    def ingest():
        payload = request.get_json(force=True, silent=True) or {}
        try:
            storage.insert_sensor_reading(payload)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True})

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
