PYTHON ?= python3

.PHONY: build-data fetch-lsoa clean

build-data:
	$(PYTHON) scripts/fetch_practices.py
	$(PYTHON) scripts/enrich_practices_lsoa.py
	$(PYTHON) scripts/fetch_availability.py
	$(PYTHON) scripts/fetch_population.py
	$(PYTHON) scripts/fetch_imd.py
	$(PYTHON) scripts/build_data.py

fetch-lsoa:
	$(PYTHON) scripts/fetch_lsoa_boundaries.py

clean:
	rm -f data/processed/practices.geojson data/processed/areas.geojson data/processed/area_metrics.json data/processed/qa_report.json
