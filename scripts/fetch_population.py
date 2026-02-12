#!/usr/bin/env python3
"""Fetch LSOA population (real Nomis data, seed fallback)."""

from __future__ import annotations

from pathlib import Path
import csv
import os
import json
import re
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

OUT = Path("data/raw/population.csv")
PRACTICES_PATH = Path("data/raw/practices.csv")
LSOA_BOUNDARIES_PATH = Path("data/raw/lsoa_boundaries.geojson")
LSOA_CODE_RE = re.compile(r"^[EW]010\d{5}$")

SEED_ROWS = [
    {
        "area_code": "AREA1",
        "area_name": "Central",
        "population_total": "26000",
        "population_adults": "18000",
        "population_children": "8000",
    },
    {
        "area_code": "AREA2",
        "area_name": "North",
        "population_total": "22000",
        "population_adults": "15000",
        "population_children": "7000",
    },
    {
        "area_code": "AREA3",
        "area_name": "West",
        "population_total": "18000",
        "population_adults": "12000",
        "population_children": "6000",
    },
]


def load_existing_rows() -> list[dict[str, str]]:
    if not OUT.exists():
        return []
    with OUT.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def looks_like_seed(rows: list[dict[str, str]]) -> bool:
    if len(rows) != len(SEED_ROWS):
        return False
    keys = {"area_code", "area_name", "population_total", "population_adults", "population_children"}
    return all(set(r.keys()) == keys for r in rows) and {r["area_code"] for r in rows} == {
        r["area_code"] for r in SEED_ROWS
    }


def write_rows(rows: list[dict[str, str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "area_code",
                "area_name",
                "population_total",
                "population_adults",
                "population_children",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def load_practice_lsoa_codes() -> list[str]:
    if not PRACTICES_PATH.exists():
        return []
    with PRACTICES_PATH.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    codes = set()
    for row in rows:
        area = (row.get("area_code") or "").strip()
        if not area.startswith("LSOA::"):
            continue
        code = area.replace("LSOA::", "", 1).strip()
        # 2021 LSOA codes for England/Wales use E/W prefix.
        if code.startswith("E") or code.startswith("W"):
            codes.add(code)
    return sorted(codes)


def load_all_lsoa_codes_from_boundaries() -> list[str]:
    if not LSOA_BOUNDARIES_PATH.exists():
        return []
    payload = json.loads(LSOA_BOUNDARIES_PATH.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    out = set()
    for feature in features:
        props = feature.get("properties", {})
        if not isinstance(props, dict):
            continue
        code = str(props.get("LSOA21CD") or props.get("LSOA11CD") or "").strip()
        if LSOA_CODE_RE.match(code):
            out.add(code)
    return sorted(out)


def fetch_nomis_population_for_codes(lsoa_codes: list[str]) -> list[dict[str, str]]:
    base = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2014_1.data.csv"
    by_lsoa: dict[str, dict[str, str]] = {}

    for batch in chunked(lsoa_codes, 150):
        params = {
            "date": "latest",
            "geography": ",".join(batch),
            "gender": "0",  # Total
            "c_age": "200,201,202",  # All ages, 0-15, 16+
            "measures": "20100",  # Value
        }
        url = f"{base}?{urlencode(params)}"
        with urlopen(url, timeout=180) as response:
            lines = response.read().decode("utf-8").splitlines()

        reader = csv.DictReader(lines)
        for row in reader:
            lsoa_code = (row.get("GEOGRAPHY_CODE") or "").strip()
            lsoa_name = (row.get("GEOGRAPHY_NAME") or "").strip()
            age_code = (row.get("C_AGE") or "").strip()
            obs_value = (row.get("OBS_VALUE") or "").strip()
            if not lsoa_code or not age_code or not obs_value:
                continue

            item = by_lsoa.setdefault(
                lsoa_code,
                {
                    "area_code": f"LSOA::{lsoa_code}",
                    "area_name": lsoa_name or lsoa_code,
                    "population_total": "0",
                    "population_adults": "0",
                    "population_children": "0",
                },
            )

            if age_code == "200":
                item["population_total"] = obs_value
            elif age_code == "201":
                item["population_children"] = obs_value
            elif age_code == "202":
                item["population_adults"] = obs_value

    return list(by_lsoa.values())


def fetch_nomis_population_for_geography(geography: str) -> list[dict[str, str]]:
    base = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2014_1.data.csv"
    params = {
        "date": "latest",
        "geography": geography,
        "gender": "0",
        "c_age": "200,201,202",
        "measures": "20100",
    }
    url = f"{base}?{urlencode(params)}"
    with urlopen(url, timeout=300) as response:
        lines = response.read().decode("utf-8").splitlines()

    by_lsoa: dict[str, dict[str, str]] = {}
    reader = csv.DictReader(lines)
    for row in reader:
        lsoa_code = (row.get("GEOGRAPHY_CODE") or "").strip()
        lsoa_name = (row.get("GEOGRAPHY_NAME") or "").strip()
        age_code = (row.get("C_AGE") or "").strip()
        obs_value = (row.get("OBS_VALUE") or "").strip()
        if not lsoa_code or not age_code or not obs_value:
            continue
        item = by_lsoa.setdefault(
            lsoa_code,
            {
                "area_code": f"LSOA::{lsoa_code}",
                "area_name": lsoa_name or lsoa_code,
                "population_total": "0",
                "population_adults": "0",
                "population_children": "0",
            },
        )
        if age_code == "200":
            item["population_total"] = obs_value
        elif age_code == "201":
            item["population_children"] = obs_value
        elif age_code == "202":
            item["population_adults"] = obs_value
    return list(by_lsoa.values())


def rows_look_like_lsoa(rows: list[dict[str, str]]) -> bool:
    if not rows:
        return False
    sample = rows[:100]
    valid = 0
    for row in sample:
        code = str(row.get("area_code", "")).replace("LSOA::", "").strip()
        if LSOA_CODE_RE.match(code):
            valid += 1
    return valid >= max(1, int(len(sample) * 0.9))


def main() -> None:
    existing_rows = load_existing_rows()
    full_geography = os.getenv("NOMIS_POPULATION_GEOGRAPHY", "").strip()
    if full_geography:
        try:
            rows = fetch_nomis_population_for_geography(full_geography)
            if rows:
                if rows_look_like_lsoa(rows):
                    write_rows(rows)
                    print(
                        f"Wrote {OUT} ({len(rows)} rows, source=nomis NM_2014_1 geography={full_geography})"
                    )
                    return
                print(
                    f"Nomis geography={full_geography} returned non-LSOA codes (e.g. {rows[0]['area_code']}); falling back to LSOA-code mode."
                )
            else:
                print("Nomis full-geography query returned zero rows; falling back.")
        except URLError as exc:
            print(f"Nomis full-geography fetch failed ({exc}); falling back.")
            if existing_rows and not looks_like_seed(existing_rows):
                print(f"Keeping existing {OUT} ({len(existing_rows)} rows) because existing data is non-seed.")
                return

    all_lsoa_codes = load_all_lsoa_codes_from_boundaries()
    if all_lsoa_codes:
        try:
            rows = fetch_nomis_population_for_codes(all_lsoa_codes)
            if rows and rows_look_like_lsoa(rows):
                write_rows(rows)
                print(
                    f"Wrote {OUT} ({len(rows)} rows, source=nomis NM_2014_1 via all LSOA boundary codes={len(all_lsoa_codes)})"
                )
                return
            print("Boundary-code population query returned no usable LSOA rows; falling back.")
        except URLError as exc:
            print(f"Boundary-code population fetch failed ({exc}); falling back.")
            if existing_rows and not looks_like_seed(existing_rows):
                print(f"Keeping existing {OUT} ({len(existing_rows)} rows) because existing data is non-seed.")
                return

    lsoa_codes = load_practice_lsoa_codes()
    if not lsoa_codes:
        if existing_rows and not looks_like_seed(existing_rows):
            print(
                f"No LSOA codes found in practices; keeping existing {OUT} ({len(existing_rows)} rows)."
            )
            return
        write_rows(SEED_ROWS)
        print("No LSOA codes found in practices; wrote seed population fallback.")
        return

    try:
        rows = fetch_nomis_population_for_codes(lsoa_codes)
        if rows:
            write_rows(rows)
            print(
                f"Wrote {OUT} ({len(rows)} rows, source=nomis NM_2014_1 targeted, requested_lsoas={len(lsoa_codes)})"
            )
            return
        print("Nomis population query returned zero rows; falling back to seed data.")
    except URLError as exc:
        print(f"Nomis population fetch failed ({exc}); falling back to seed data.")
        if existing_rows and not looks_like_seed(existing_rows):
            print(f"Keeping existing {OUT} ({len(existing_rows)} rows) because existing data is non-seed.")
            return

    write_rows(SEED_ROWS)
    print(f"Wrote {OUT} ({len(SEED_ROWS)} rows, source=seed)")


if __name__ == "__main__":
    main()
