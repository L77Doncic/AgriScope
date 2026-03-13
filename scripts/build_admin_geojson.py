import argparse
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

BASE = "https://geo.datav.aliyun.com/areas_v3/bound"
UA = {"User-Agent": "Mozilla/5.0"}
CACHE_DIR = "data/admin_cache"
PROVINCES_PATH = os.path.join(CACHE_DIR, "provinces.json")
DONE_PATH = os.path.join(CACHE_DIR, "done.json")
FEATURES_PATH = os.path.join(CACHE_DIR, "features.jsonl")
PROVINCE_NAMES = {}


def fetch_json(url: str, retries: int = 3, delay: float = 1.0) -> Dict[str, Any]:
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except Exception as exc:
            last = exc
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def out_of_china(lon: float, lat: float) -> bool:
    return lon < 72.004 or lon > 137.8347 or lat < 0.8293 or lat > 55.8271


def _transform_lat(x: float, y: float) -> float:
    import math
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * (abs(x) ** 0.5)
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    import math
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * (abs(x) ** 0.5)
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lon: float, lat: float) -> Tuple[float, float]:
    if out_of_china(lon, lat):
        return lon, lat
    import math
    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    mglat = lat + dlat
    mglon = lon + dlon
    return lon * 2 - mglon, lat * 2 - mglat


def transform_coords(coords):
    if isinstance(coords[0], (float, int)):
        lon, lat = coords
        wlon, wlat = gcj02_to_wgs84(lon, lat)
        return [wlon, wlat]
    return [transform_coords(c) for c in coords]


def normalize_feature(feature: Dict[str, Any], province_name: str, city_name: str) -> Dict[str, Any]:
    props = feature.get("properties", {})
    adcode = props.get("adcode")
    name = props.get("name")
    level = props.get("level")
    parent = props.get("parent", {}) or {}

    geometry = feature.get("geometry")
    if geometry:
        geometry = {
            "type": geometry.get("type"),
            "coordinates": transform_coords(geometry.get("coordinates")),
        }

    center = props.get("center")
    if center:
        center = list(gcj02_to_wgs84(center[0], center[1]))
    centroid = props.get("centroid")
    if centroid:
        centroid = list(gcj02_to_wgs84(centroid[0], centroid[1]))

    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "adcode": adcode,
            "level": level,
            "parent_adcode": parent.get("adcode"),
            "province_name": province_name,
            "city_name": city_name,
            "center": center,
            "centroid": centroid,
        },
        "geometry": geometry,
    }


def load_done() -> List[int]:
    if not os.path.exists(DONE_PATH):
        return []
    with open(DONE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_done(done: List[int]) -> None:
    with open(DONE_PATH, "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False)


def ensure_cache() -> List[Dict[str, Any]]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(PROVINCES_PATH):
        with open(PROVINCES_PATH, "r", encoding="utf-8") as f:
            provinces = json.load(f)
            _build_province_names(provinces)
            return provinces
    china = fetch_json(f"{BASE}/100000_full.json")
    provinces = china.get("features", [])
    with open(PROVINCES_PATH, "w", encoding="utf-8") as f:
        json.dump(provinces, f, ensure_ascii=False)
    _build_province_names(provinces)
    return provinces


def _build_province_names(provinces: List[Dict[str, Any]]) -> None:
    for prov in provinces:
        props = prov.get("properties", {})
        code = props.get("adcode")
        name = props.get("name")
        if code and name:
            PROVINCE_NAMES[int(code)] = name


def append_features(features: List[Dict[str, Any]]) -> None:
    if not features:
        return
    with open(FEATURES_PATH, "a", encoding="utf-8") as f:
        for feature in features:
            f.write(json.dumps(feature, ensure_ascii=False))
            f.write("\n")


def process_province(prov_code: int, sleep_s: float) -> int:
    province_name = PROVINCE_NAMES.get(prov_code, str(prov_code))
    try:
        prov_data = fetch_json(f"{BASE}/{prov_code}_full.json")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"skip province {prov_code}: 404")
            return 0
        raise
    except RuntimeError as e:
        if "HTTP Error 404" in str(e):
            print(f"skip province {prov_code}: 404")
            return 0
        raise
    sub = prov_data.get("features", [])
    if not sub:
        return 0
    first_level = sub[0].get("properties", {}).get("level")
    out: List[Dict[str, Any]] = []
    if first_level == "district":
        for f in sub:
            out.append(normalize_feature(f, province_name, province_name))
        append_features(out)
        return len(out)
    if first_level == "city":
        for city in sub:
            city_code = city.get("properties", {}).get("adcode")
            city_name = city.get("properties", {}).get("name") or str(city_code)
            if not city_code:
                continue
            try:
                city_data = fetch_json(f"{BASE}/{city_code}_full.json")
            except Exception:
                continue
            districts = city_data.get("features", [])
            for d in districts:
                out.append(normalize_feature(d, province_name, city_name))
            time.sleep(sleep_s)
        append_features(out)
        return len(out)
    return 0


def finalize(output_path: str) -> None:
    features = []
    if os.path.exists(FEATURES_PATH):
        with open(FEATURES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                features.append(json.loads(line))
    geojson = {"type": "FeatureCollection", "features": features}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-provinces", type=int, default=5)
    parser.add_argument("--all", action="store_true", help="process all provinces in one run")
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.2, help="sleep seconds between city fetches")
    args = parser.parse_args()

    provinces = ensure_cache()
    done = load_done()

    if args.finalize:
        finalize("static/geo/china_admin_sample.geojson")
        return

    count = 0
    for prov in provinces:
        prov_code = prov.get("properties", {}).get("adcode")
        if not prov_code or prov_code in done:
            continue
        added = process_province(prov_code, args.sleep)
        done.append(prov_code)
        save_done(done)
        count += 1
        print(f"processed province {prov_code}, added {added}")
        if not args.all and count >= args.max_provinces:
            break

    if args.all:
        finalize("static/geo/china_admin_sample.geojson")


if __name__ == "__main__":
    main()
