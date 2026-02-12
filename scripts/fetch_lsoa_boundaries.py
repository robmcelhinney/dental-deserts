#!/usr/bin/env python3
"""Fetch LSOA boundaries GeoJSON from a configurable source URL."""

from __future__ import annotations

from pathlib import Path
import gzip
import json
import os
from urllib.request import Request, urlopen

OUT = Path("data/raw/lsoa_boundaries.geojson")


def main() -> None:
    source_url = os.getenv("LSOA_BOUNDARIES_URL", "").strip()
    if not source_url:
        print("Skipped LSOA boundaries fetch; set LSOA_BOUNDARIES_URL to enable.")
        return

    request = Request(source_url, headers={"Accept": "application/json,*/*"})
    with urlopen(request, timeout=120) as response:
        raw = response.read()

    if source_url.endswith(".gz"):
        raw = gzip.decompress(raw)

    payload = json.loads(raw.decode("utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError("LSOA boundary source is not a GeoJSON FeatureCollection")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT} ({len(payload.get('features', []))} features)")


if __name__ == "__main__":
    main()
