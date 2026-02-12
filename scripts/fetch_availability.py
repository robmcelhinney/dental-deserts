#!/usr/bin/env python3
"""Fetch NHS availability from normalized snapshot; seed fallback for local dev."""

from __future__ import annotations

from pathlib import Path
import csv

from nhs_live import read_normalized_snapshot

OUT = Path("data/raw/availability.csv")

SEED_ROWS = [
    {
        "practice_id": "P001",
        "accepting_adults": "yes",
        "accepting_children": "yes",
        "last_reported": "2026-02-01",
    },
    {
        "practice_id": "P002",
        "accepting_adults": "no",
        "accepting_children": "yes",
        "last_reported": "2026-02-01",
    },
    {
        "practice_id": "P003",
        "accepting_adults": "unknown",
        "accepting_children": "unknown",
        "last_reported": "2026-02-01",
    },
    {
        "practice_id": "P004",
        "accepting_adults": "yes",
        "accepting_children": "no",
        "last_reported": "2026-02-01",
    },
    {
        "practice_id": "P005",
        "accepting_adults": "no",
        "accepting_children": "no",
        "last_reported": "2026-02-01",
    },
]


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


def main() -> None:
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

    write_csv(SEED_ROWS)
    print(f"Wrote {OUT} ({len(SEED_ROWS)} rows, source=seed)")


if __name__ == "__main__":
    main()
