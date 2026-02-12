# NHS Dental Desert — Roadmap & Planning Guide (Markdown)

> Goal: a postcode-driven web app that shows **NHS dental access** around a user, including **reported accepting adults/children**, **distance/travel**, and **area-level pressure/need** (population + deprivation), presented honestly with clear caveats.

---

## ✅ 0) Project setup and scope

- [x] Write a 1–2 paragraph **problem statement** ("Finding an NHS dentist is hard; this visualises access using public data.")
- [x] Define **MVP** vs **V1** vs **V2** (use the sections below)
- [x] Choose a license (MIT/Apache) and create repo structure:
    - [x] `/frontend`
    - [x] `/data`
    - [x] `/scripts`
    - [x] `/docs`

- [x] Pick deployment target(s):
    - [x] Static frontend hosting (e.g., Cloudflare Pages / Netlify / GitHub Pages)
    - [x] Optional backend/API hosting (e.g., Fly.io / Render / Hetzner)

- [x] Define success criteria:
    - [x] Postcode search reliably centers map
    - [x] Practices load fast (<2s for initial render on broadband)
    - [x] Clear "reported availability" disclaimers everywhere relevant
    - [x] Reproducible data pipeline (one command to rebuild)

---

## ✅ 1) Data discovery and design

### 1.1 Identify datasets and fields (don’t code yet)

- [x] List candidate datasets and what they provide:
    - [x] **NHS dental practices list** (name, address/postcode, identifier)
    - [x] **"Accepting new NHS patients"** (adult/children flags; self-reported)
    - [x] **Population** by area (LSOA/MSOA/LA)
    - [x] **Deprivation (IMD)** (area-level index/deciles)
    - [x] Optional: oral health indicators (area-level)

- [ ] Decide your **geographic unit** for area overlays:
    - [ ] LSOA (fine-grained, great for maps)
    - [ ] MSOA/Local Authority (simpler, less granular)

- [x] Define your **core entities** and IDs:
    - [x] `practice_id` (stable)
    - [x] `practice_postcode`
    - [x] `lat`, `lon`
    - [x] `accepting_adults` / `accepting_children` / `unknown`
    - [x] `area_code` (LSOA/MSOA/etc)

- [x] Write a data dictionary in `/docs/data-dictionary.md`
- [x] Define your "truth and caveats" messaging:
    - [x] Availability is **reported** and may be outdated
    - [x] "Accepting" ≠ quick appointments
    - [x] Map shows **access** not quality

### 1.2 Data model & outputs

- [x] Decide final data artifacts:
    - [x] `practices.geojson` (or `.json` with coords) for frontend
    - [x] `areas.geojson` for choropleth overlay
    - [x] `area_metrics.json` keyed by `area_code`

- [ ] Decide update strategy:
    - [ ] Manual monthly rebuild
    - [ ] Automated scheduled build (optional)

---

## ✅ 2) Data pipeline (repeatable + auditable)

> Target outcome: `make build-data` produces final artifacts from raw sources.

### 2.1 Raw data ingestion

- [x] Create `/data/raw/` and `/scripts/`
- [x] Add a script to download or import each dataset:
    - [x] `scripts/fetch_practices.*`
    - [x] `scripts/fetch_availability.*`
    - [x] `scripts/fetch_population.*`
    - [x] `scripts/fetch_imd.*`

- [x] Add provenance notes:
    - [x] `/docs/sources.md` with dataset names, dates retrieved, and licenses

### 2.2 Cleaning + normalisation

- [x] Normalise postcodes (uppercase, trim, standard formatting)
- [x] Deduplicate practices (same address/name variations)
- [x] Validate required fields exist:
    - [x] `practice_name`
    - [x] `postcode`
    - [x] `accepting_*` fields (or `unknown`)

- [x] Log warnings, don’t silently drop records:
    - [x] Missing postcode
    - [x] Invalid postcode pattern
    - [x] Missing availability status

### 2.3 Geocoding practices (UK postcodes)

- [x] Implement postcode → lat/lon enrichment using `postcodes.io`
- [x] Add caching to avoid hammering API:
    - [x] Cache file: `/data/cache/postcodes.json`

- [x] Handle geocoding failures:
    - [x] Mark as `geocode_failed=true`
    - [x] Exclude from map but include in QA report

### 2.4 Area join (LSOA/MSOA) for metrics

- [x] Choose method to assign practices to areas:
    - [x] Join via postcode → area code (if available)
    - [ ] Or spatial join lat/lon → polygons (more robust)

- [x] Produce `area_metrics.json`:
    - [x] practices per 10k population
    - [x] "accepting adults" practices per 10k adults (if adult pop available)
    - [x] "accepting children" per 10k children (if child pop available)
    - [x] deprivation decile

- [x] Produce a QA report:
    - [x] Count practices total / geocoded / availability known
    - [x] Top areas with missing data
    - [x] Summary stats (min/median/max distances between practices)

### 2.5 Build artifacts and size optimisation

- [x] Convert to compact format:
    - [x] Minified JSON
    - [x] GeoJSON simplification for polygons

- [ ] Ensure map assets are reasonable size:
    - [ ] Practices dataset ideally < 5–10MB
    - [ ] Area polygons simplified enough for smooth pan/zoom

---

## ✅ 3) Product design (what users can do)

### 3.1 MVP user journey (must be great)

- [x] User enters postcode → map centers on location
- [x] Map shows nearest practices with icons:
    - [x] Accepting adults ✅ / ❌ / unknown
    - [x] Accepting children ✅ / ❌ / unknown

- [x] Sidebar list sorted by distance with:
    - [x] name, distance, availability flags, address

- [x] Click practice → popup with details + "Open in Google Maps" link (optional)
- [x] Clear disclaimer shown near results

### 3.2 V1 features (makes it "shareable")

- [x] Add radius filters: 1km / 2km / 5km / 10km
- [x] Add "adult vs children" toggle (primary interaction)
- [x] Show "Dental desert" banner:
    - [x] "No practices reporting adult availability within X km"

- [x] Add area overlay toggle:
    - [x] Choropleth of access pressure (e.g., practices per 10k)

- [x] Add "How unusual is this?" compare card:
    - [x] show percentile for user’s area vs national distribution

### 3.3 V2 features (advanced / optional)

- [ ] Travel-time isochrones (if you add routing)
- [ ] Trend over time (if you store monthly snapshots)
- [ ] Accessibility info (wheelchair access if dataset exists)
- [ ] API endpoint for programmatic queries

---

## ✅ 4) Frontend implementation (Leaflet + CDN + OSM)

### 4.1 Basic app scaffold

- [x] Create a simple static web app (no framework required)
- [x] Load Leaflet from CDN
- [x] Load OSM tiles with attribution
- [x] Set up layout:
    - [x] map panel
    - [x] sidebar results
    - [x] filter controls

### 4.2 Postcode search + geocoding

- [x] Input field + button + enter-to-search
- [x] Call `postcodes.io` to geocode user-entered postcode
- [x] Validate postcode input and show friendly errors
- [x] Cache last searched postcode in localStorage

### 4.3 Render practices

- [x] Load practices JSON/GeoJSON
- [x] Render markers with clustering (recommended)
- [x] Marker icon style reflects adult/child availability
- [x] Clicking marker highlights the sidebar item and vice versa

### 4.4 Distance + ranking logic

- [x] Compute distance from searched point to each practice (Haversine)
- [x] Filter by radius
- [x] Show "nearest N" (e.g., 25) and allow "load more"

### 4.5 Area overlay (choropleth)

- [x] Load simplified `areas.geojson`
- [x] Load `area_metrics.json`
- [x] Choropleth by selected metric:
    - [x] access pressure
    - [x] accepting adults density
    - [x] deprivation decile (optional)

- [x] Hover tooltip shows area summary
- [x] Legend component with clear labels (no misleading precision)

### 4.6 UX and accessibility polish

- [x] Mobile layout works (map + collapsible sheet)
- [x] Keyboard focus styles for inputs and list items
- [x] "Loading…" and error states (no silent failures)
- [x] Always show attribution + data source links

---

## ✅ 5) Backend (optional, but useful)

> You can do a **fully static** version first. Backend becomes useful for: fast search, rate limiting, analytics, and hiding API keys (if any).

- [x] Decide: static-only vs thin API
- [ ] If API:
    - [ ] Endpoint: `/api/nearby?lat=&lon=&radius=&adultOnly=`
    - [ ] Pre-index practices by geohash or k-d tree for speed
    - [ ] Return sorted list + summary stats

- [ ] Add basic caching headers (CDN friendly)

---

## ✅ 6) QA, correctness, and "honesty checks"

### 6.1 Data QA

- [ ] Verify geocoding success rate is acceptable (target > 95%)
- [ ] Spot-check random postcodes on map match reality
- [ ] Verify availability flags appear plausible (not all unknown)
- [ ] Confirm all disclaimers match dataset limitations

### 6.2 UX QA

- [ ] Try 10 postcodes across:
    - [ ] London
    - [ ] rural England
    - [ ] Scotland
    - [ ] Wales
    - [ ] Northern Ireland (confirm dataset coverage; label if partial)

- [ ] Ensure map works on:
    - [ ] desktop Chrome/Firefox
    - [ ] mobile Safari/Chrome

### 6.3 Performance QA

- [ ] Lighthouse run and fix big issues
- [ ] Ensure datasets are compressed and cached
- [ ] Ensure clustering prevents sluggishness

---

## ✅ 7) Deployment and operations

- [ ] Choose hosting and deploy frontend
- [ ] Configure caching headers for static assets
- [ ] Add a `/status` page or simple "data last updated" footer
- [ ] Add analytics (privacy-friendly) (optional)
- [ ] Add error logging (optional)

---

## ✅ 8) Documentation (what makes it portfolio-grade)

- [x] `README.md` includes:
    - [ ] what it does (screenshots/GIF)
    - [x] data sources summary
    - [x] how to rebuild data
    - [x] limitations and caveats

- [x] `/docs/methodology.md`:
    - [x] how "dental deserts" are defined
    - [x] how radius filtering works
    - [x] how per-capita metrics are computed

- [x] `/docs/ethics.md`:
    - [x] no ranking of "good/bad" practices
    - [x] "reported availability" explanation
    - [x] avoidance of naming-and-shaming

- [x] Add an explicit "Not medical advice" / "Not appointment availability" note

---

## ✅ 9) MVP checklist (ship this first)

- [x] Practice dataset imported + geocoded
- [x] Postcode search centers map
- [x] Nearest practices listed with distance
- [x] Adult/child availability toggle
- [x] "No adult availability within X km" message
- [x] Basic disclaimer + sources link
- [ ] Deployed publicly with "last updated" date

---

## ✅ 10) V1 "this is genuinely useful" checklist

- [x] Choropleth overlay (access pressure)
- [x] Dental desert heat/overlay mode
- [x] Area compare card (percentile)
- [x] Mobile-friendly UI
- [x] Fast performance with clustering
- [x] Rebuild pipeline documented and repeatable

---

## ✅ 11) V2 stretch checklist

- [ ] Monthly snapshotting + trend charts
- [ ] Better routing/travel time mode
- [ ] "Notify me if an area changes" (if you add a backend + cron)
- [ ] Public API / downloadable dataset export (if licensing permits)

---

## Suggested milestone schedule (fast but realistic)

- [x] **Milestone A (Data foundations):** pipeline produces clean geocoded practices dataset + QA report
- [x] **Milestone B (MVP app):** postcode search + map + list + filters deployed
- [x] **Milestone C (V1 insights):** dental deserts + area overlay + compare card
- [x] **Milestone D (Polish + docs):** portfolio-grade README + methodology + ethics

---

If you want, I can also give you a **recommended repo layout + exact JSON shapes** for `practices` and `area_metrics`, so the frontend work is dead straightforward.
