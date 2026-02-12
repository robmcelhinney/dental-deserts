# NHS Dental Deserts

A postcode-driven web app to visualize NHS dental access near a user, including reported acceptance of new NHS adults/children, distance to nearby practices, and area-level access pressure and deprivation context.

Finding an NHS dentist is difficult and often opaque. This project makes public data easier to explore, while explicitly showing uncertainty: reported acceptance can be out of date, and acceptance does not imply immediate appointment availability.

## Scope

- `MVP`: postcode search, nearest practices by distance, adult/children acceptance flags, disclaimer, and deployed static app.
- `V1`: radius filters, children/adults toggle, dental-desert banner, choropleth overlays, area comparison card.
- `V2`: travel-time mode, trends over time, optional API and notifications.

## Repo Layout

- `frontend/`: static web app (Leaflet + OSM)
- `data/seed/`: committed fallback seed inputs used when live fetches fail
- `data/raw/`: generated fetch artifacts (git-ignored)
- `data/cache/`: postcode geocoding cache
- `data/processed/`: frontend-ready artifacts committed and deployed by GitHub Pages
- `scripts/`: reproducible data pipeline scripts
- `docs/`: methodology, ethics, source notes, and data dictionary

## Build Data

```bash
make build-data
```

This command rebuilds:

- `data/processed/practices.geojson`
- `data/processed/areas.geojson`
- `data/processed/area_metrics.json`
- `data/processed/qa_report.json`

It refreshes local fetch artifacts in `data/raw/` (for example
`practices.csv`, `availability.csv`, `population.csv`, and `imd.csv`), which
are intentionally git-ignored to avoid commit churn. Seed fallback inputs are
kept in `data/seed/`.

## Deploy To GitHub Pages

This repo includes a GitHub Actions workflow at
`.github/workflows/deploy-gh-pages.yml` that deploys on pushes to `main`.

The deploy workflow:

- Does not run `make build-data`.
- Validates that committed `data/processed/` artifacts are present.
- Publishes `frontend/` at the site root (`/`) and includes committed `data/processed/`.

## Use Live NHS Data

The pipeline supports official NHS Service Search API ingestion.

1. Obtain an NHS API subscription key.
2. Export it in your shell:

```bash
export NHS_API_SUBSCRIPTION_KEY=\"<your-key>\"
```

3. Run:

```bash
make build-data
```

Quick sanity check before running:

```bash
echo ${#NHS_API_SUBSCRIPTION_KEY}
```

This should print a non-zero number.

Optional env vars:

- `NHS_SERVICE_SEARCH_URL` (default: `https://int.api.service.nhs.uk/service-search-api`)
- `NHS_SERVICE_SEARCH_API_VERSION` (default: `3`)
- `NHS_SERVICE_SEARCH_QUERY` (default: `dentist`)
- `NHS_SERVICE_SEARCH_PAGE_SIZE` (default: `200`)
- `NHS_SERVICE_SEARCH_MAX_PAGES` (default: `80`)

If no key is present, the scripts intentionally fall back to seed data for local development.

## Area Metrics (MSOA)

- `make build-data` runs `scripts/enrich_practices_lsoa.py` to attach LSOA codes from postcodes (via `postcodes.io`) to practices.
- `scripts/fetch_population.py` pulls real LSOA population denominators from Nomis dataset `NM_2014_1` (2021-based small area estimates), with seed fallback only on request failure.
- `scripts/build_data.py` aggregates those LSOA denominators and practice counts into MSOA-level metrics for the compare card and overlays.
- Overlay is intentionally off by default because current area polygons are synthetic unless real boundaries are supplied.
- To start using real polygons, set:

```bash
export LSOA_BOUNDARIES_URL="<geojson-or-geojson.gz-url>"
make fetch-lsoa
```

Or download from: https://geoportal.statistics.gov.uk/datasets/ons::lower-layer-super-output-areas-december-2021-boundaries-ew-bsc-v4-2/explore

This writes `data/raw/lsoa_boundaries.geojson`, which `scripts/build_data.py` will use when area codes match.

## England-only Coverage

Current overlay/benchmark coverage is England-only by design in this repo build.

Why:

- The current processed geometry/metric pipeline is keyed to England MSOA conventions (`MSOA::E...`) and England-focused denominator joins.
- Cross-nation comparability is non-trivial: data definitions, update cadence, and publication structures differ across England, Wales, Scotland, and Northern Ireland.
- To avoid misleading comparisons, unsupported areas are shown with clear warnings instead of mixed-quality metrics.

Planned expansion path:

- Add nation-specific boundary + denominator + deprivation ingestion for Wales, Scotland, and Northern Ireland.
- Normalize to a common area schema with explicit provenance/version metadata per nation.
- Ship side-by-side QA checks before enabling UK-wide overlay comparisons in production.

## Limitations and Caveats

- Availability fields are reported values and may be stale.
- "Accepting NHS patients" is not equivalent to short waits.
- This map is an access exploration tool, not a quality ranking.
- Live NHS clinic data is used when `NHS_API_SUBSCRIPTION_KEY` is available.
- Seed data remains as a fallback path, and some non-NHS inputs may still be seed-backed depending on pipeline configuration.

## License

MIT (`LICENSE`).
