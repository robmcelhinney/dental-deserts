#!/usr/bin/env python3
"""Fetch NHS dental practices (live when configured, seed fallback otherwise)."""

from __future__ import annotations

from pathlib import Path
import csv
import os

from nhs_live import (
    fetch_nhs_service_search_pages,
    normalize_nhs_records,
    write_normalized_snapshot,
)

OUT = Path("data/raw/practices.csv")
NORMALIZED_SNAPSHOT = Path("data/raw/nhs_practices_normalized.json")
SEED_PATH = Path("data/seed/practices.csv")


def write_csv(rows: list[dict[str, str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "practice_id",
                "practice_name",
                "address",
                "postcode",
                "lat",
                "lon",
                "area_code",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def load_existing_rows() -> list[dict[str, str]]:
    if not OUT.exists():
        return []
    with OUT.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_seed_rows() -> list[dict[str, str]]:
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_PATH}")
    with SEED_PATH.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def looks_like_seed(rows: list[dict[str, str]], seed_rows: list[dict[str, str]]) -> bool:
    if len(rows) != len(seed_rows):
        return False
    names = {r.get("practice_name", "").strip() for r in rows}
    seed_names = {r.get("practice_name", "").strip() for r in seed_rows}
    return names == seed_names


def main() -> None:
    seed_rows = load_seed_rows()
    use_live = bool(os.getenv("NHS_API_SUBSCRIPTION_KEY", "").strip())
    existing_rows = load_existing_rows()

    if use_live:
        try:
            items = fetch_nhs_service_search_pages()
            normalized = normalize_nhs_records(items)
            if normalized:
                write_normalized_snapshot(normalized)
                rows = [
                    {
                        "practice_id": row["practice_id"],
                        "practice_name": row["practice_name"],
                        "address": row["address"],
                        "postcode": row["postcode"],
                        "lat": row.get("lat", ""),
                        "lon": row.get("lon", ""),
                        "area_code": row.get("area_code", ""),
                    }
                    for row in normalized
                ]
                write_csv(rows)
                print(f"Wrote {OUT} ({len(rows)} rows, source=nhs-api)")
                return

            print("NHS API returned no normalized dental records; falling back to seed rows.")
        except Exception as exc:  # pragma: no cover
            print(f"Live NHS fetch failed ({exc}); falling back to seed rows.")

        # Safety: do not wipe existing real data with 5-row seed fallback.
        if existing_rows and not looks_like_seed(existing_rows, seed_rows):
            print(
                f"Keeping existing {OUT} ({len(existing_rows)} rows) because live fetch failed and existing data is non-seed."
            )
            return

    write_normalized_snapshot([])
    write_csv(seed_rows)
    print(f"Wrote {OUT} ({len(seed_rows)} rows, source=seed)")


if __name__ == "__main__":
    main()
