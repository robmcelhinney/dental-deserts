# Methodology

## Access Definition

The app estimates access using three components:

- Proximity to practices (distance from searched postcode).
- Reported acceptance flags for adults and children.
- Area-level supply pressure (`practices_per_10k`) and deprivation context (`imd_decile`).

## Distance Calculation

Distances are computed with the Haversine formula from searched coordinates to each geocoded practice point.

## Per-Capita Metrics

For each area:

- `practices_per_10k = practice_count / population_total * 10000`
- `accepting_adults_per_10k_adults = accepting_adults_count / population_adults * 10000`
- `accepting_children_per_10k_children = accepting_children_count / population_children * 10000`

## Data Integrity Rules

- Normalize postcodes (uppercase, remove spaces).
- Deduplicate by `(practice_name, postcode_norm)`.
- Log missing/invalid postcodes and missing availability.
- Keep non-geocoded records in QA output.
