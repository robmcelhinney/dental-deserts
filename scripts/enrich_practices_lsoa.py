#!/usr/bin/env python3
"""Enrich practices with LSOA names from postcodes.io bulk lookup."""

from __future__ import annotations

from pathlib import Path
import csv
import json
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

PRACTICES_PATH = Path("data/raw/practices.csv")
CACHE_PATH = Path("data/cache/postcode_lsoa.json")
LSOA_BOUNDARIES_PATH = Path("data/raw/lsoa_boundaries.geojson")
LSOA_CODE_RE = re.compile(r"^[EW]010\d{5}$")


def normalize_postcode(postcode: str) -> str:
    return re.sub(r"\s+", "", postcode.strip().upper())


def load_cache() -> dict[str, dict[str, str]]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, dict[str, str]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_postcodes_lsoa(postcodes: list[str]) -> dict[str, dict[str, str]]:
    endpoint = "https://api.postcodes.io/postcodes"
    payload = json.dumps({"postcodes": postcodes}).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))

    results: dict[str, dict[str, str]] = {}
    for item in body.get("result", []):
        query = normalize_postcode(str(item.get("query", "")))
        result = item.get("result") or {}
        codes = result.get("codes") or {}
        lsoa = str(result.get("lsoa") or "").strip()
        msoa = str(result.get("msoa") or "").strip()
        lsoa_code = str(codes.get("lsoa") or "").strip()
        msoa_code = str(codes.get("msoa") or "").strip()
        results[query] = {
            "lsoa": lsoa,
            "msoa": msoa,
            "lsoa_code": lsoa_code,
            "msoa_code": msoa_code,
        }
    return results


def load_lsoa_name_to_code() -> dict[str, str]:
    if not LSOA_BOUNDARIES_PATH.exists():
        return {}
    payload = json.loads(LSOA_BOUNDARIES_PATH.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    lookup: dict[str, str] = {}
    for feature in features:
        props = feature.get("properties", {})
        if not isinstance(props, dict):
            continue
        code = str(props.get("LSOA21CD") or props.get("LSOA11CD") or "").strip()
        name = str(props.get("LSOA21NM") or props.get("LSOA11NM") or "").strip()
        if code and name:
            lookup[name] = code
            lookup[name.upper()] = code
    return lookup


def cached_has_canonical_lsoa(cache_entry: dict[str, str]) -> bool:
    code = str(cache_entry.get("lsoa_code") or "").strip()
    if LSOA_CODE_RE.match(code):
        return True
    lsoa = str(cache_entry.get("lsoa") or "").strip()
    return LSOA_CODE_RE.match(lsoa) is not None


def main() -> None:
    if not PRACTICES_PATH.exists():
        print(f"Skipped LSOA enrichment; {PRACTICES_PATH} not found.")
        return

    with PRACTICES_PATH.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    cache = load_cache()
    lsoa_name_to_code = load_lsoa_name_to_code()
    needed = sorted(
        {
            normalize_postcode(row.get("postcode", ""))
            for row in rows
            if normalize_postcode(row.get("postcode", ""))
            and not cached_has_canonical_lsoa(
                cache.get(normalize_postcode(row.get("postcode", "")), {})
            )
        }
    )

    fetched = 0
    if needed:
        for batch in chunked(needed, 100):
            try:
                result = fetch_postcodes_lsoa(batch)
                cache.update(result)
                fetched += len(batch)
            except URLError as exc:
                print(f"LSOA lookup warning: {exc}. Continuing with cached values.")
                break

    updated = 0
    for row in rows:
        postcode_norm = normalize_postcode(row.get("postcode", ""))
        if not postcode_norm:
            continue
        cached = cache.get(postcode_norm, {})
        lsoa = cached.get("lsoa", "")
        lsoa_code = str(cached.get("lsoa_code") or "").strip()
        existing_area = row.get("area_code", "").strip()
        if lsoa and (not existing_area or existing_area.startswith("COUNTY::")):
            code = ""
            if LSOA_CODE_RE.match(lsoa_code):
                code = lsoa_code
            elif LSOA_CODE_RE.match(str(lsoa)):
                code = str(lsoa)
            else:
                code = lsoa_name_to_code.get(lsoa) or lsoa_name_to_code.get(lsoa.upper()) or ""
            row["area_code"] = f"LSOA::{code}" if code else f"LSOA::{lsoa}"
            updated += 1

    if rows:
        fieldnames = list(rows[0].keys())
        with PRACTICES_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    save_cache(cache)
    print(f"LSOA enrichment complete: updated={updated}, fetched_postcodes={fetched}, cache_size={len(cache)}")


if __name__ == "__main__":
    main()
