# Data Dictionary

## Core Entities

### Practice

- `practice_id`: stable unique ID for a practice.
- `practice_name`: human-readable name.
- `address`: free-text street address.
- `postcode`: original postcode text.
- `postcode_norm`: normalized postcode (uppercase, spaces removed).
- `lat`: latitude in WGS84.
- `lon`: longitude in WGS84.
- `area_code`: mapped area ID (LSOA/MSOA/placeholder in scaffold).
- `accepting_adults`: `yes`/`no`/`unknown`.
- `accepting_children`: `yes`/`no`/`unknown`.
- `geocode_failed`: boolean indicating lookup failure.

### Area Metric

- `area_code`: area identifier.
- `area_name`: display name.
- `population_total`: total population.
- `population_adults`: adult population denominator.
- `population_children`: children population denominator.
- `practice_count`: total practices assigned to area.
- `accepting_adults_count`: practices reporting adult acceptance.
- `accepting_children_count`: practices reporting children acceptance.
- `practices_per_10k`: total practices per 10,000 population.
- `accepting_adults_per_10k_adults`: adult-accepting practices per 10,000 adults.
- `accepting_children_per_10k_children`: child-accepting practices per 10,000 children.
- `imd_decile`: deprivation decile (1 most deprived to 10 least deprived).

## Artifacts

- `data/processed/practices.geojson`: map points for practices.
- `data/processed/areas.geojson`: area polygons for choropleth.
- `data/processed/area_metrics.json`: keyed metrics by `area_code`.
- `data/processed/qa_report.json`: counts, warning summaries, and distance stats.
