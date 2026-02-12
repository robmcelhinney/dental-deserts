#!/usr/bin/env python3
"""Build postcode lookup CSV from data/raw/practices.csv without network access."""

from __future__ import annotations

from pathlib import Path
import csv


SRC = Path("data/raw/practices.csv")
DST = Path("data/raw/postcode_lookup.csv")


def normalize_postcode(value: str) -> str:
    return "".join(value.strip().upper().split())


def main() -> None:
    rows: list[dict[str, str]] = []
    if SRC.exists():
        with SRC.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                postcode = normalize_postcode(str(row.get("postcode") or ""))
                lat = str(row.get("lat") or "").strip()
                lon = str(row.get("lon") or "").strip()
                area_code = str(row.get("area_code") or "").strip()
                if postcode and lat and lon:
                    rows.append(
                        {
                            "postcode": postcode,
                            "lat": lat,
                            "lon": lon,
                            "area_code": area_code,
                        }
                    )

    dedup = {row["postcode"]: row for row in rows}
    DST.parent.mkdir(parents=True, exist_ok=True)
    with DST.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["postcode", "lat", "lon", "area_code"])
        writer.writeheader()
        writer.writerows(dedup.values())
    print(f"Wrote {DST} ({len(dedup)} rows, source=practices)")


if __name__ == "__main__":
    main()
