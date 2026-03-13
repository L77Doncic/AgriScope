import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    device_id TEXT,
                    admin_code TEXT,
                    lat REAL,
                    lon REAL,
                    payload TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    prediction REAL,
                    suggestion TEXT,
                    features TEXT
                )
                """
            )

    def insert_sensor_reading(self, payload: Dict[str, Any]) -> None:
        ts = payload.get("ts") or datetime.now(timezone.utc).isoformat()
        device_id = payload.get("device_id", "dev-test")
        admin_code = payload.get("admin_code", "")
        lat = payload.get("lat", 0)
        lon = payload.get("lon", 0)
        payload.setdefault("soil_moisture", 0)
        payload.setdefault("temperature", 0)
        payload.setdefault("rainfall", 0)
        payload.setdefault("nitrogen", 0)
        raw = json.dumps(payload, ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sensor_readings (ts, device_id, admin_code, lat, lon, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, device_id, admin_code, lat, lon, raw),
            )

    def insert_prediction(self, features: Dict[str, Any], prediction: float, suggestion: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        raw = json.dumps(features, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO predictions (ts, prediction, suggestion, features)
                VALUES (?, ?, ?, ?)
                """,
                (ts, float(prediction), suggestion, raw),
            )

    def get_latest_readings(self, admin_code: str, limit: int = 200) -> List[Dict[str, Any]]:
        query = "SELECT ts, device_id, admin_code, lat, lon, payload FROM sensor_readings"
        params = []
        if admin_code:
            query += " WHERE admin_code = ?"
            params.append(admin_code)
        query += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)

        rows = []
        with self._connect() as conn:
            for row in conn.execute(query, params):
                payload = json.loads(row[5]) if row[5] else {}
                rows.append(
                    {
                        "ts": row[0],
                        "device_id": row[1],
                        "admin_code": row[2],
                        "lat": row[3],
                        "lon": row[4],
                        "payload": payload,
                    }
                )
        return rows
