#!/usr/bin/env python3
"""Build processed datasets used by the frontend and QA workflow."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
import csv
import json
import re
from urllib.error import URLError
from urllib.request import urlopen

RAW_DIR = Path("data/raw")
PROC_DIR = Path("data/processed")
CACHE_PATH = Path("data/cache/postcodes.json")
LSOA_CACHE_PATH = Path("data/cache/postcode_lsoa.json")

POSTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2}$")
LSOA_CODE_RE = re.compile(r"^[EW]010\d{5}$")


@dataclass
class Practice:
    practice_id: str
    practice_name: str
    address: str
    postcode: str
    postcode_norm: str
    lat: float | None
    lon: float | None
    area_code: str | None
    geocode_failed: bool
    accepting_adults: str
    accepting_children: str


def normalize_postcode(postcode: str) -> str:
    return re.sub(r"\s+", "", postcode.strip().upper())


def canonical_lsoa_area_code(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("LSOA::"):
        code = text.replace("LSOA::", "", 1).strip()
    else:
        code = text
    if LSOA_CODE_RE.match(code):
        return f"LSOA::{code}"
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_lsoa_boundaries() -> dict[str, dict]:
    path = RAW_DIR / "lsoa_boundaries.geojson"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    out: dict[str, dict] = {}
    code_keys = ("LSOA11CD", "LSOA21CD", "lsoa_code", "code", "area_code")
    name_keys = ("LSOA11NM", "LSOA21NM", "lsoa_name", "name", "area_name")

    for feature in features:
        props = feature.get("properties", {})
        if not isinstance(props, dict):
            continue
        area_code = None
        for key in code_keys:
            value = props.get(key)
            if isinstance(value, str) and value.strip():
                area_code = value.strip()
                break
        if not area_code:
            continue
        area_name = None
        for key in name_keys:
            value = props.get(key)
            if isinstance(value, str) and value.strip():
                area_name = value.strip()
                break
        feature_obj = {
            "type": "Feature",
            "id": area_code,
            "properties": {
                "area_code": area_code,
                "area_name": area_name or area_code,
            },
            "geometry": feature.get("geometry"),
        }
        out[area_code] = feature_obj
        if area_name:
            out[area_name] = feature_obj
            out[area_name.upper()] = feature_obj
    return out


def load_lsoa_boundary_rows() -> list[dict[str, object]]:
    path = RAW_DIR / "lsoa_boundaries.geojson"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    out: list[dict[str, object]] = []
    code_keys = ("LSOA11CD", "LSOA21CD", "lsoa_code", "code", "area_code")
    name_keys = ("LSOA11NM", "LSOA21NM", "lsoa_name", "name", "area_name")

    for feature in features:
        props = feature.get("properties", {})
        if not isinstance(props, dict):
            continue
        lsoa_code = ""
        for key in code_keys:
            value = props.get(key)
            if isinstance(value, str) and value.strip():
                lsoa_code = value.strip()
                break
        if not lsoa_code:
            continue
        lsoa_name = ""
        for key in name_keys:
            value = props.get(key)
            if isinstance(value, str) and value.strip():
                lsoa_name = value.strip()
                break
        out.append(
            {
                "lsoa_code": lsoa_code,
                "lsoa_name": lsoa_name,
                "geometry": feature.get("geometry"),
            }
        )
    return out


def load_msoa_boundary_rows() -> list[dict[str, object]]:
    candidates = [
        RAW_DIR / "msoa_boundaries.geojson",
        RAW_DIR / "Middle_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V3_4916445166053426.geojson",
    ]
    path = None
    for candidate in candidates:
        if candidate.exists():
            path = candidate
            break
    if path is None:
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    out: list[dict[str, object]] = []
    code_keys = ("MSOA11CD", "MSOA21CD", "msoa_code", "code", "area_code")
    name_keys = ("MSOA11NM", "MSOA21NM", "msoa_name", "name", "area_name")

    for feature in features:
        props = feature.get("properties", {})
        if not isinstance(props, dict):
            continue
        msoa_code = ""
        for key in code_keys:
            value = props.get(key)
            if isinstance(value, str) and value.strip():
                msoa_code = value.strip()
                break
        msoa_name = ""
        for key in name_keys:
            value = props.get(key)
            if isinstance(value, str) and value.strip():
                msoa_name = value.strip()
                break
        if not msoa_name and not msoa_code:
            continue
        out.append(
            {
                "msoa_code": msoa_code,
                "msoa_name": msoa_name,
                "geometry": feature.get("geometry"),
            }
        )
    return out


def load_postcode_lsoa_cache() -> dict[str, dict[str, str]]:
    if not LSOA_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(LSOA_CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def load_practice_lsoa_to_msoa_map() -> dict[str, str]:
    path = RAW_DIR / "practices.csv"
    if not path.exists():
        return {}

    cache = load_postcode_lsoa_cache()
    if not cache:
        return {}

    with path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_lsoa: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        postcode_norm = normalize_postcode(row.get("postcode", ""))
        if not postcode_norm:
            continue
        cached = cache.get(postcode_norm) or {}
        msoa_name = str(cached.get("msoa") or "").strip()
        if not msoa_name:
            continue
        lsoa_code = lsoa_code_from_area((row.get("area_code") or "").strip())
        if not lsoa_code:
            continue
        by_lsoa[lsoa_code][msoa_name] += 1

    out: dict[str, str] = {}
    for lsoa_code, counts in by_lsoa.items():
        out[lsoa_code] = counts.most_common(1)[0][0]
    return out


def load_lookup() -> dict[str, dict[str, str]]:
    rows = read_csv(RAW_DIR / "postcode_lookup.csv")
    return {row["postcode"]: row for row in rows}


def geocode_postcode_live(postcode_norm: str) -> dict[str, str] | None:
    endpoint = f"https://api.postcodes.io/postcodes/{postcode_norm}"
    try:
        with urlopen(endpoint, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload.get("result")
        if not result:
            return None
        return {
            "lat": str(result["latitude"]),
            "lon": str(result["longitude"]),
            "area_code": str(result.get("lsoa") or ""),
        }
    except (URLError, TimeoutError, ValueError, KeyError):
        return None


def load_cache() -> dict[str, dict[str, str]]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, dict[str, str]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")


def build_practices() -> tuple[list[Practice], dict[str, int], list[str]]:
    practices_raw = read_csv(RAW_DIR / "practices.csv")
    availability_raw = {row["practice_id"]: row for row in read_csv(RAW_DIR / "availability.csv")}
    lookup = load_lookup()
    cache = load_cache()

    warnings: list[str] = []
    warning_counts = Counter()
    results: list[Practice] = []
    seen = set()

    for row in practices_raw:
        practice_id = row["practice_id"].strip()
        key = (row["practice_name"].strip().lower(), normalize_postcode(row["postcode"]))
        if key in seen:
            warning_counts["deduplicated_practices"] += 1
            continue
        seen.add(key)

        postcode_norm = normalize_postcode(row["postcode"])
        if not postcode_norm:
            warning_counts["missing_postcode"] += 1
            warnings.append(f"{practice_id}: missing postcode")
            continue
        if not POSTCODE_RE.match(postcode_norm):
            warning_counts["invalid_postcode"] += 1
            warnings.append(f"{practice_id}: invalid postcode '{row['postcode']}'")
            continue

        availability = availability_raw.get(practice_id)
        if availability is None:
            warning_counts["missing_availability"] += 1
            availability = {
                "accepting_adults": "unknown",
                "accepting_children": "unknown",
            }

        lat = lon = None
        area_code = None
        geocode_failed = True

        # Prefer source coordinates when available (e.g., NHS Service Search v3).
        src_lat = row.get("lat", "").strip()
        src_lon = row.get("lon", "").strip()
        src_area = row.get("area_code", "").strip()
        src_area_canonical = canonical_lsoa_area_code(src_area)
        if src_lat and src_lon:
            try:
                lat = float(src_lat)
                lon = float(src_lon)
                area_code = src_area_canonical or (src_area or None)
                geocode_failed = False
                cache[postcode_norm] = {
                    "lat": f"{lat}",
                    "lon": f"{lon}",
                    "area_code": area_code or "",
                }
            except ValueError:
                lat = lon = None
                area_code = None
                geocode_failed = True

        geocode = None
        if geocode_failed:
            geocode = cache.get(postcode_norm) or lookup.get(postcode_norm) or geocode_postcode_live(postcode_norm)

        if geocode and geocode_failed:
            lat = float(geocode["lat"])
            lon = float(geocode["lon"])
            geocode_area = str(geocode.get("area_code") or "").strip()
            geocode_area_canonical = canonical_lsoa_area_code(geocode_area)
            area_code = src_area_canonical or geocode_area_canonical or (src_area or None)
            geocode_failed = False
            cache[postcode_norm] = {
                "lat": f"{lat}",
                "lon": f"{lon}",
                "area_code": area_code or "",
            }
        elif geocode_failed:
            warning_counts["geocode_failed"] += 1
            warnings.append(f"{practice_id}: geocode lookup failed for {postcode_norm}")

        results.append(
            Practice(
                practice_id=practice_id,
                practice_name=row["practice_name"].strip(),
                address=row["address"].strip(),
                postcode=row["postcode"].strip().upper(),
                postcode_norm=postcode_norm,
                lat=lat,
                lon=lon,
                area_code=area_code,
                geocode_failed=geocode_failed,
                accepting_adults=availability.get("accepting_adults", "unknown").strip().lower(),
                accepting_children=availability.get("accepting_children", "unknown").strip().lower(),
            )
        )

    save_cache(cache)
    return results, dict(warning_counts), warnings


def write_practices_geojson(practices: list[Practice]) -> None:
    features = []
    for p in practices:
        if p.geocode_failed or p.lat is None or p.lon is None:
            continue
        lsoa_code = lsoa_code_from_area(p.area_code)
        if lsoa_code and LSOA_CODE_RE.match(lsoa_code) and not is_england_lsoa_code(lsoa_code):
            continue
        features.append(
            {
                "type": "Feature",
                "id": p.practice_id,
                "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
                "properties": {
                    "practice_id": p.practice_id,
                    "practice_name": p.practice_name,
                    "address": p.address,
                    "postcode": p.postcode,
                    "area_code": p.area_code,
                    "accepting_adults": p.accepting_adults,
                    "accepting_children": p.accepting_children,
                },
            }
        )

    obj = {"type": "FeatureCollection", "features": features}
    (PROC_DIR / "practices.geojson").write_text(
        json.dumps(obj, separators=(",", ":")), encoding="utf-8"
    )


def derive_msoa_name_from_lsoa_name(lsoa_name: str) -> str | None:
    text = (lsoa_name or "").strip()
    if not text:
        return None
    # Typical pattern: "Wandsworth 026B" -> "Wandsworth 026"
    match = re.match(r"^(.*\b\d{3})[A-Z]$", text)
    if match:
        return match.group(1).strip()
    return None


def msoa_key_from_name(msoa_name: str) -> str:
    return f"MSOA::{msoa_name}"


def msoa_key_from_code(msoa_code: str) -> str:
    return f"MSOA::{msoa_code}"


def lsoa_code_from_area(area_code: str | None) -> str | None:
    if not area_code:
        return None
    value = area_code.strip()
    if value.startswith("LSOA::"):
        value = value.replace("LSOA::", "", 1).strip()
    if value:
        return value
    return None


def is_england_lsoa_code(lsoa_code: str | None) -> bool:
    return bool(lsoa_code and lsoa_code.startswith("E"))


def is_england_msoa_code(msoa_code: str | None) -> bool:
    return bool(msoa_code and msoa_code.startswith("E"))


def is_england_msoa_key(msoa_key: str | None) -> bool:
    return bool(msoa_key and msoa_key.startswith("MSOA::E"))


def write_areas_and_metrics(practices: list[Practice]) -> dict[str, dict[str, float | int | str]]:
    population_rows = read_csv(RAW_DIR / "population.csv")
    imd_rows = {r["area_code"]: int(r["imd_decile"]) for r in read_csv(RAW_DIR / "imd.csv")}
    msoa_boundary_rows = load_msoa_boundary_rows()
    msoa_name_to_code = {
        str(row.get("msoa_name") or "").strip().upper(): str(row.get("msoa_code") or "").strip()
        for row in msoa_boundary_rows
        if str(row.get("msoa_name") or "").strip() and str(row.get("msoa_code") or "").strip()
    }
    lsoa_to_msoa_from_practices = load_practice_lsoa_to_msoa_map()
    lsoa_to_msoa: dict[str, str] = {}
    msoa_names_by_key: dict[str, str] = {}
    msoa_population = defaultdict(
        lambda: {"population_total": 0, "population_adults": 0, "population_children": 0}
    )
    msoa_imd_weighted = defaultdict(lambda: {"weighted_sum": 0.0, "weight": 0})

    for row in population_rows:
        lsoa_area = (row.get("area_code") or "").strip()
        lsoa_code = lsoa_code_from_area(lsoa_area)
        if not is_england_lsoa_code(lsoa_code):
            continue
        lsoa_name = (row.get("area_name") or "").strip()
        msoa_name = lsoa_to_msoa_from_practices.get(lsoa_code) or derive_msoa_name_from_lsoa_name(lsoa_name)
        if not lsoa_code or not msoa_name:
            continue

        msoa_code = msoa_name_to_code.get(msoa_name.upper(), "")
        msoa_key = msoa_key_from_code(msoa_code) if msoa_code else msoa_key_from_name(msoa_name)
        if not is_england_msoa_key(msoa_key):
            continue
        lsoa_to_msoa[lsoa_code] = msoa_key
        if msoa_name:
            msoa_names_by_key[msoa_key] = msoa_name

        pop_total = int(row["population_total"])
        pop_adults = int(row["population_adults"])
        pop_children = int(row["population_children"])
        msoa_population[msoa_key]["population_total"] += pop_total
        msoa_population[msoa_key]["population_adults"] += pop_adults
        msoa_population[msoa_key]["population_children"] += pop_children

        imd_value = (
            imd_rows.get(lsoa_area)
            or imd_rows.get(lsoa_code)
            or imd_rows.get(f"LSOA::{lsoa_code}")
        )
        if imd_value is not None and pop_total > 0:
            msoa_imd_weighted[msoa_key]["weighted_sum"] += imd_value * pop_total
            msoa_imd_weighted[msoa_key]["weight"] += pop_total

    counts = defaultdict(lambda: {"total": 0, "adults_yes": 0, "children_yes": 0})
    practice_centroids: dict[str, tuple[float, float]] = {}
    grouped = defaultdict(list)

    for p in practices:
        lsoa_code = lsoa_code_from_area(p.area_code)
        if not is_england_lsoa_code(lsoa_code):
            continue
        if not lsoa_code:
            continue
        msoa_key = lsoa_to_msoa.get(lsoa_code)
        if not msoa_key:
            continue
        counts[msoa_key]["total"] += 1
        if p.accepting_adults == "yes":
            counts[msoa_key]["adults_yes"] += 1
        if p.accepting_children == "yes":
            counts[msoa_key]["children_yes"] += 1
        if p.lat is not None and p.lon is not None and not p.geocode_failed:
            grouped[msoa_key].append((p.lat, p.lon))

    for area_code, coords in grouped.items():
        avg_lat = sum(lat for lat, _ in coords) / len(coords)
        avg_lon = sum(lon for _, lon in coords) / len(coords)
        practice_centroids[area_code] = (avg_lat, avg_lon)

    metrics: dict[str, dict[str, float | int | str]] = {}
    for msoa_key, pop in msoa_population.items():
        area_name = msoa_names_by_key.get(msoa_key, msoa_key.replace("MSOA::", ""))
        practice_count = counts[msoa_key]["total"]
        adults_yes = counts[msoa_key]["adults_yes"]
        children_yes = counts[msoa_key]["children_yes"]

        pop_total = int(pop["population_total"])
        pop_adults = int(pop["population_adults"])
        pop_children = int(pop["population_children"])
        practices_per_10k = round(practice_count / pop_total * 10000, 4) if pop_total else 0.0
        adults_per_10k = round(adults_yes / pop_adults * 10000, 4) if pop_adults else 0.0
        children_per_10k = round(children_yes / pop_children * 10000, 4) if pop_children else 0.0

        imd_weight = msoa_imd_weighted[msoa_key]["weight"]
        if imd_weight > 0:
            imd_decile: str | int = int(
                round(msoa_imd_weighted[msoa_key]["weighted_sum"] / imd_weight)
            )
        else:
            imd_decile = "unknown"

        metrics[msoa_key] = {
            "area_code": msoa_key,
            "area_name": area_name,
            "population_total": pop_total,
            "population_adults": pop_adults,
            "population_children": pop_children,
            "practice_count": practice_count,
            "accepting_adults_count": adults_yes,
            "accepting_children_count": children_yes,
            "practices_per_10k": practices_per_10k,
            "accepting_adults_per_10k_adults": adults_per_10k,
            "accepting_children_per_10k_children": children_per_10k,
            "imd_decile": imd_decile,
        }

    for area_code, area_counts in counts.items():
        if area_code in metrics:
            continue
        if not is_england_msoa_key(area_code):
            continue
        metrics[area_code] = {
            "area_code": area_code,
            "area_name": area_code.replace("MSOA::", ""),
            "population_total": 0,
            "population_adults": 0,
            "population_children": 0,
            "practice_count": area_counts["total"],
            "accepting_adults_count": area_counts["adults_yes"],
            "accepting_children_count": area_counts["children_yes"],
            "practices_per_10k": 0.0,
            "accepting_adults_per_10k_adults": 0.0,
            "accepting_children_per_10k_children": 0.0,
            "imd_decile": "unknown",
        }

    areas_features = []
    if msoa_boundary_rows:
        metrics_by_name = {str(v["area_name"]).strip().upper(): k for k, v in metrics.items()}
        for row in msoa_boundary_rows:
            msoa_code = str(row.get("msoa_code") or "").strip()
            if msoa_code and not is_england_msoa_code(msoa_code):
                continue
            msoa_name = str(row.get("msoa_name") or "").strip()
            if not msoa_name and not msoa_code:
                continue
            msoa_key = None
            if msoa_code:
                code_key = msoa_key_from_code(msoa_code)
                if code_key in metrics:
                    msoa_key = code_key
            if msoa_key is None and msoa_name:
                msoa_key = metrics_by_name.get(msoa_name.upper()) or msoa_key_from_name(msoa_name)
            if msoa_key not in metrics:
                continue
            areas_features.append(
                {
                    "type": "Feature",
                    "id": str(msoa_code or msoa_key),
                    "properties": {
                        "area_code": msoa_key,
                        "area_name": metrics[msoa_key]["area_name"],
                        "imd_decile": metrics[msoa_key]["imd_decile"],
                    },
                    "geometry": row.get("geometry"),
                }
            )
    else:
        boundary_rows = load_lsoa_boundary_rows()
        if boundary_rows:
            for row in boundary_rows:
                lsoa_name = str(row.get("lsoa_name") or "").strip()
                msoa_name = derive_msoa_name_from_lsoa_name(lsoa_name)
                if not msoa_name:
                    continue
                msoa_key = msoa_key_from_name(msoa_name)
                if msoa_key not in metrics:
                    continue
                areas_features.append(
                    {
                        "type": "Feature",
                        "id": str(row.get("lsoa_code") or msoa_key),
                        "properties": {
                            "area_code": msoa_key,
                            "area_name": metrics[msoa_key]["area_name"],
                            "imd_decile": metrics[msoa_key]["imd_decile"],
                        },
                        "geometry": row.get("geometry"),
                    }
                )

    # Synthetic fallback when no boundaries are available.
    if not areas_features:
        for i, area_code in enumerate(metrics):
            area_name = str(metrics[area_code]["area_name"])
            center_lat, center_lon = practice_centroids.get(area_code, (51.0 + i * 0.02, -1.0 - i * 0.02))
            radius_km = 4.0
            steps = 18
            coords = []
            for step in range(steps):
                angle = 2 * 3.141592653589793 * (step / steps)
                dlat = radius_km / 111.0
                dlon = dlat / max(cos(radians(center_lat)), 0.25)
                lat = center_lat + dlat * sin(angle)
                lon = center_lon + dlon * cos(angle)
                coords.append([lon, lat])
            coords.append(coords[0])
            areas_features.append(
                {
                    "type": "Feature",
                    "id": area_code,
                    "properties": {
                        "area_code": area_code,
                        "area_name": area_name,
                        "imd_decile": metrics[area_code]["imd_decile"],
                    },
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                }
            )

    (PROC_DIR / "area_metrics.json").write_text(
        json.dumps(metrics, separators=(",", ":")), encoding="utf-8"
    )
    (PROC_DIR / "areas.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": areas_features}, separators=(",", ":")),
        encoding="utf-8",
    )
    return metrics


def build_qa(practices: list[Practice], warning_counts: dict[str, int], warnings: list[str]) -> None:
    geocoded = [p for p in practices if not p.geocode_failed and p.lat is not None and p.lon is not None]
    known_availability = [
        p
        for p in geocoded
        if p.accepting_adults in {"yes", "no"} or p.accepting_children in {"yes", "no"}
    ]

    distances = []
    for i, p1 in enumerate(geocoded):
        for p2 in geocoded[i + 1 :]:
            distances.append(haversine_km(p1.lat, p1.lon, p2.lat, p2.lon))

    if distances:
        distances_sorted = sorted(distances)
        mid = len(distances_sorted) // 2
        median = (
            distances_sorted[mid]
            if len(distances_sorted) % 2 == 1
            else (distances_sorted[mid - 1] + distances_sorted[mid]) / 2
        )
        dist_summary = {
            "min_km": round(min(distances_sorted), 3),
            "median_km": round(median, 3),
            "max_km": round(max(distances_sorted), 3),
        }
    else:
        dist_summary = {"min_km": None, "median_km": None, "max_km": None}

    top_missing = [w for w in warnings[:10]]
    missing_by_area = Counter(
        p.area_code or "unassigned" for p in practices if p.geocode_failed or p.area_code is None
    )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "practices_total": len(practices),
            "practices_geocoded": len(geocoded),
            "practices_availability_known": len(known_availability),
        },
        "geocoding_success_rate": round((len(geocoded) / len(practices) * 100) if practices else 0, 2),
        "warning_counts": warning_counts,
        "top_missing_data_examples": top_missing,
        "top_areas_with_missing_data": missing_by_area.most_common(10),
        "distance_summary_between_practices": dist_summary,
    }

    (PROC_DIR / "qa_report.json").write_text(
        json.dumps(report, separators=(",", ":")), encoding="utf-8"
    )


def main() -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    practices, warning_counts, warnings = build_practices()
    write_practices_geojson(practices)
    write_areas_and_metrics(practices)
    build_qa(practices, warning_counts, warnings)
    print("Built data/processed/{practices.geojson,areas.geojson,area_metrics.json,qa_report.json}")


if __name__ == "__main__":
    main()
