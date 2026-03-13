import json
import os
import random
import time
from datetime import datetime, timezone

import requests


def main():
    url = os.getenv("INGEST_URL", "http://127.0.0.1:5000/api/ingest")
    admin_code = os.getenv("ADMIN_CODE", "110105")
    device_id = os.getenv("DEVICE_ID", "sim-001")
    interval = float(os.getenv("INTERVAL_SEC", "5"))

    while True:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id,
            "admin_code": admin_code,
            "lat": float(os.getenv("LAT", "39.95")),
            "lon": float(os.getenv("LON", "116.40")),
            "soil_moisture": round(random.uniform(0.15, 0.55), 3),
            "temperature": round(random.uniform(8, 28), 2),
            "rainfall": round(random.uniform(0, 5), 2),
            "nitrogen": round(random.uniform(0.1, 0.6), 3),
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception:
            pass
        time.sleep(interval)


if __name__ == "__main__":
    main()
