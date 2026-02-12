#!/usr/bin/env python3
"""Fetch NHS availability from normalized snapshot; seed fallback for local dev."""

from __future__ import annotations

from pathlib import Path
import csv

from nhs_live import read_normalized_snapshot

OUT = Path("data/raw/availability.csv")
SEED_PATH = Path("data/seed/availability.csv")


def write_csv(rows: list[dict[str, str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "practice_id",
                "accepting_adults",
                "accepting_children",
                "last_reported",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def load_seed_rows() -> list[dict[str, str]]:
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_PATH}")
    with SEED_PATH.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    seed_rows = load_seed_rows()
    normalized = read_normalized_snapshot()
    rows = [
        {
            "practice_id": row.get("practice_id", ""),
            "accepting_adults": row.get("accepting_adults", "unknown"),
            "accepting_children": row.get("accepting_children", "unknown"),
            "last_reported": row.get("last_reported", ""),
        }
        for row in normalized
        if row.get("practice_id")
    ]

    if rows:
        write_csv(rows)
        print(f"Wrote {OUT} ({len(rows)} rows, source=normalized)")
        return

    write_csv(seed_rows)
    print(f"Wrote {OUT} ({len(seed_rows)} rows, source=seed)")


if __name__ == "__main__":
    main()
