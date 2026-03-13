import csv
import json
from typing import Dict, Tuple


def normalize_code(code: str) -> str:
    code = code.strip()
    if not code:
        return ""
    if len(code) >= 6:
        return code[:6]
    return code.zfill(6)


def load_area_codes(path: str) -> Dict[str, str]:
    for encoding in ("utf-8-sig", "gb18030", "gbk"):
        try:
            with open(path, "r", encoding=encoding) as f:
                reader = csv.reader(f)
                data = {}
                for row in reader:
                    if not row:
                        continue
                    code = normalize_code(row[0])
                    name = row[1].strip() if len(row) > 1 else ""
                    if code and name:
                        data[code] = name
                return data
        except UnicodeDecodeError:
            continue
    raise RuntimeError("Failed to decode area code CSV.")


def code_prefixes(adcode: str) -> Tuple[str, str, str]:
    ad6 = normalize_code(adcode)
    prov = ad6[:2] + "0000"
    city = ad6[:4] + "00"
    return prov, city, ad6


def main():
    geo_path = "static/geo/china_admin_sample.geojson"
    csv_path = "data/area_code_2024.csv"

    code_map = load_area_codes(csv_path)

    with open(geo_path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    updated = 0
    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        adcode = str(props.get("adcode", ""))
        if not adcode:
            continue
        prov, city, dist = code_prefixes(adcode)
        province_name = props.get("province_name") or code_map.get(prov)
        city_name = props.get("city_name") or code_map.get(city)
        district_name = props.get("name") or code_map.get(dist)

        if province_name:
            props["province_name"] = province_name
        if city_name:
            props["city_name"] = city_name
        if district_name:
            props["name"] = district_name

        feature["properties"] = props
        updated += 1

    with open(geo_path, "w", encoding="utf-8") as f:
        json.dump(geo, f, ensure_ascii=False)

    print(f"Updated {updated} features.")


if __name__ == "__main__":
    main()
