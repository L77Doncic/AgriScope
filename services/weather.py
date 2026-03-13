import math
import os
from typing import Dict, List

import requests


class WeatherProvider:
    def __init__(self):
        self.provider = os.getenv("WEATHER_PROVIDER", "open_meteo")
        self.api_key = os.getenv("WEATHER_API_KEY", "")

    def get_realtime(self, lat: float, lon: float) -> Dict:
        if self.provider == "open_meteo":
            return self._open_meteo(lat, lon)
        if self.provider == "era5":
            return self._era5_placeholder(lat, lon)
        return {"provider": self.provider, "error": "unknown provider"}

    def _open_meteo(self, lat: float, lon: float) -> Dict:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,relative_humidity_2m,et0_fao_evapotranspiration",
            "hourly": "shortwave_radiation,precipitation,relative_humidity_2m,et0_fao_evapotranspiration",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {"provider": "open_meteo", "data": data}

    def _era5_placeholder(self, lat: float, lon: float) -> Dict:
        return {
            "provider": "era5",
            "note": "Configure ERA5 API access and replace this method.",
            "lat": lat,
            "lon": lon,
        }

    @staticmethod
    def generate_grid(min_lon: float, min_lat: float, max_lon: float, max_lat: float, resolution_km: float) -> List[Dict]:
        grid = []
        lat_step = resolution_km / 110.574
        lat = min_lat
        while lat < max_lat:
            lon_step = resolution_km / (111.320 * math.cos(math.radians(lat)) + 1e-6)
            lon = min_lon
            while lon < max_lon:
                grid.append(
                    {
                        "bbox": [lon, lat, min(lon + lon_step, max_lon), min(lat + lat_step, max_lat)],
                        "center": [lon + lon_step / 2, lat + lat_step / 2],
                    }
                )
                lon += lon_step
            lat += lat_step
        return grid
