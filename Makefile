PYTHON ?= python3
ENV_LOAD = set -a; [ -f .env ] && . ./.env; set +a;

.PHONY: build-data fetch-lsoa clean

build-data:
	@$(ENV_LOAD) $(PYTHON) scripts/fetch_practices.py
	@$(ENV_LOAD) $(PYTHON) scripts/enrich_practices_lsoa.py
	@$(ENV_LOAD) $(PYTHON) scripts/fetch_availability.py
	@$(ENV_LOAD) $(PYTHON) scripts/fetch_population.py
	@$(ENV_LOAD) $(PYTHON) scripts/fetch_imd.py
	@$(ENV_LOAD) $(PYTHON) scripts/build_data.py

fetch-lsoa:
	@$(ENV_LOAD) $(PYTHON) scripts/fetch_lsoa_boundaries.py

clean:
	rm -f data/processed/practices.geojson data/processed/areas.geojson data/processed/area_metrics.json data/processed/qa_report.json
