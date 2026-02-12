# Sources and Provenance

This scaffold uses deterministic seed data by default, but now includes a live connector for NHS Service Search API when credentials are configured.

## Active/Planned Production Sources

- NHS Service Search API:
    - Publisher: NHS England / NHS API platform
    - Endpoint: `https://api.nhs.uk/service-search/search-postcode-or-place`
    - Auth: `subscription-key` required
    - Used for: practice identity, location fields, and any available adult/children acceptance indicators
- Nomis API (ONS):
    - Dataset: `NM_2014_1` (Population estimates - small area, 2021-based)
    - Endpoint: `https://www.nomisweb.co.uk/api/v01/dataset/NM_2014_1.data.csv`
    - Used for: LSOA-level `population_total`, `population_children` (0-15), `population_adults` (16+)
- IMD (Index of Multiple Deprivation) release tables (planned replacement for seed)
- Optional oral health indicators (public health profiles)

## Retrieval Metadata Template

When production connectors are added, track:

- dataset name
- publisher
- URL
- retrieval date (UTC)
- license
- transform notes
