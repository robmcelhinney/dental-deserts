#!/usr/bin/env python3
"""Fetch real IMD deciles (IoD 2025) keyed by LSOA code, with seed fallback."""

from __future__ import annotations

from pathlib import Path
import csv
import os
from urllib.error import URLError
from urllib.request import urlopen

IMD_OUT = Path("data/raw/imd.csv")
POSTCODE_OUT = Path("data/raw/postcode_lookup.csv")
PRACTICES_PATH = Path("data/raw/practices.csv")
SEED_PATH = Path("data/seed/imd.csv")

def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_existing_imd_rows() -> list[dict[str, str]]:
    if not IMD_OUT.exists():
        return []
    with IMD_OUT.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_seed_rows() -> list[dict[str, str]]:
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_PATH}")
    with SEED_PATH.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_imd_rows() -> list[dict[str, str]]:
    default_url = (
        "https://assets.publishing.service.gov.uk/media/691ded56d140bbbaa59a2a7d/"
        "File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
    )
    source_url = os.getenv("IMD_SOURCE_URL", default_url).strip() or default_url

    with urlopen(source_url, timeout=180) as response:
        text = response.read().decode("utf-8")

    rows = list(csv.DictReader(text.splitlines()))
    out: list[dict[str, str]] = []

    code_col = "LSOA code (2021)"
    decile_col = "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)"

    for row in rows:
        code = (row.get(code_col) or "").strip()
        decile = (row.get(decile_col) or "").strip()
        if not code or not decile:
            continue
        out.append({"area_code": f"LSOA::{code}", "imd_decile": decile})

    return out


def normalize_postcode(value: str) -> str:
    return "".join(value.strip().upper().split())


def build_postcode_lookup_rows() -> list[dict[str, str]]:
    if not PRACTICES_PATH.exists():
        return []

    with PRACTICES_PATH.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    dedup: dict[str, dict[str, str]] = {}
    for row in rows:
        postcode = normalize_postcode(str(row.get("postcode") or ""))
        lat = str(row.get("lat") or "").strip()
        lon = str(row.get("lon") or "").strip()
        area_code = str(row.get("area_code") or "").strip()
        if not postcode or not lat or not lon:
            continue
        dedup[postcode] = {
            "postcode": postcode,
            "lat": lat,
            "lon": lon,
            "area_code": area_code,
        }

    return list(dedup.values())


def main() -> None:
    seed_rows = load_seed_rows()
    existing_imd_rows = load_existing_imd_rows()
    try:
        imd_rows = fetch_imd_rows()
        if imd_rows:
            write_csv(IMD_OUT, imd_rows, ["area_code", "imd_decile"])
            print(f"Wrote {IMD_OUT} ({len(imd_rows)} rows, source=IoD 2025)")
        else:
            if existing_imd_rows:
                print(
                    f"IMD source returned no rows; keeping existing {IMD_OUT} ({len(existing_imd_rows)} rows)."
                )
            else:
                write_csv(IMD_OUT, seed_rows, ["area_code", "imd_decile"])
                print("IMD source returned no rows and no existing file; wrote seed fallback.")
    except URLError as exc:
        if existing_imd_rows:
            print(f"IMD fetch failed ({exc}); keeping existing {IMD_OUT} ({len(existing_imd_rows)} rows).")
        else:
            write_csv(IMD_OUT, seed_rows, ["area_code", "imd_decile"])
            print(f"IMD fetch failed ({exc}) and no existing file; wrote seed fallback.")

    postcode_rows = build_postcode_lookup_rows()
    if postcode_rows:
        write_csv(POSTCODE_OUT, postcode_rows, ["postcode", "lat", "lon", "area_code"])
        print(f"Wrote {POSTCODE_OUT} ({len(postcode_rows)} rows, source=practices)")
    else:
        write_csv(POSTCODE_OUT, [], ["postcode", "lat", "lon", "area_code"])
        print(f"Wrote {POSTCODE_OUT} (0 rows, source=empty)")


if __name__ == "__main__":
    main()
