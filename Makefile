.PHONY: lint test ci daily-olx-rent daily-olx-sale daily-olx daily-olx-parse daily-olx-sink-bigquery show-data dbt-debug dbt-build dbt-run dbt-test bigquery-bootstrap daily-olx-bigquery-rent daily-olx-bigquery-sale daily-olx-bigquery

COV_MIN := 70
UA := Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36
OLX_BASE_URL := https://www.olx.pl/nieruchomosci
FETCH_FLAGS := --fail --silent --show-error --location --retry 3 --retry-delay 2 --connect-timeout 10 --max-time 45
DBT_DIR := packages/analytics/dbt
DBT_PROFILES_DIR ?= $(DBT_DIR)
DBT_VARS ?= {"bronze_dataset":"bronze","silver_dataset":"silver","gold_dataset":"gold"}
BQ_PROJECT ?=
BQ_DATASET ?= bronze
BQ_LOCATION ?= EU
# Approximate 30 km coverage around Krakow, configurable per run:
# make daily-olx CITIES="krakow wieliczka skawina"
CITIES ?= krakow wieliczka skawina niepolomice zabierzow zielonki swiatniki-gorne
# "All non-commercial housing types" in OLX categories for v1:
PROPERTY_TYPES_RENT ?= mieszkania domy pokoje
PROPERTY_TYPES_SALE ?= mieszkania domy
PAGES ?= 30
DATE ?= $(shell date +%F)
ENRICH_PAUSE_MS ?= 250

lint:
	uv run ruff check .

test:
	uv run pytest --cov=domus_dweller --cov-report=term-missing --cov-fail-under=$(COV_MIN)

ci: lint test

define run_olx_job
	@mkdir -p data/raw/$(DATE) data/parsed/$(DATE)
	@echo "Starting OLX $(1) run for $(DATE) (pages=$(PAGES), cities=$(words $(CITIES)))"
	@set -e; \
	for city in $(CITIES); do \
		for property in $(3); do \
			seed="$${property}_$${city}"; \
			if [ "$$property" = "pokoje" ]; then \
				category_slug="stancje-pokoje"; \
			else \
				category_slug="$$property"; \
			fi; \
			if [ "$$category_slug" = "stancje-pokoje" ]; then \
				base_url="$(OLX_BASE_URL)/$${category_slug}/$${city}/"; \
			else \
				base_url="$(OLX_BASE_URL)/$${category_slug}/$(2)/$${city}/"; \
			fi; \
			echo "[OLX $(1)] Seed $$seed"; \
			for i in $$(seq 1 $(PAGES)); do \
				raw="data/raw/$(DATE)/olx_$(1)_$${seed}_page_$$i.html"; \
				parsed="data/parsed/$(DATE)/olx_$(1)_$${seed}_page_$$i.json"; \
				echo "[OLX $(1)] Fetch $$seed page $$i/$(PAGES)"; \
				if ! curl $(FETCH_FLAGS) -A "$(UA)" -o "$$raw" "$${base_url}?page=$$i"; then \
					echo "[OLX $(1)] Fetch failed for $$seed page $$i, stopping this seed"; \
					rm -f "$$raw" "$$parsed"; \
					break; \
				fi; \
				echo "[OLX $(1)] Parse $$seed page $$i/$(PAGES)"; \
				uv run python -m domus_dweller.parse --source olx --input "$$raw" --output "$$parsed"; \
				if [ "$$(wc -c < "$$parsed")" -le 3 ]; then \
					echo "[OLX $(1)] Empty parsed page at $$seed page $$i, stopping this seed"; \
					rm -f "$$raw" "$$parsed"; \
					break; \
				fi; \
			done; \
		done; \
	done
	@echo "[OLX $(1)] Merge search pages"
	@uv run python -m domus_dweller.merge_pages --pattern "data/parsed/$(DATE)/olx_$(1)_*_page_*.json" --output data/parsed/$(DATE)/olx_$(1)_all.json
	@echo "Finished OLX $(1) run for $(DATE)"
endef

daily-olx-rent:
	$(call run_olx_job,rent,wynajem,$(PROPERTY_TYPES_RENT))

daily-olx-sale:
	$(call run_olx_job,sale,sprzedaz,$(PROPERTY_TYPES_SALE))

daily-olx: daily-olx-rent daily-olx-sale

daily-olx-parse: daily-olx

daily-olx-sink-bigquery:
	@test -n "$(BQ_PROJECT)" || (echo "Set BQ_PROJECT=<gcp-project-id>"; exit 1)
	@attempt=1; \
	until uv run python -m domus_dweller.sinks.olx_files_to_bigquery --mode both --project "$(BQ_PROJECT)" --dataset "$(BQ_DATASET)" --date "$(DATE)"; do \
		if [ $$attempt -ge 3 ]; then \
			echo "BigQuery sink failed after $$attempt attempts"; \
			exit 1; \
		fi; \
		delay=$$((attempt * 10)); \
		echo "Retrying sink in $$delay seconds (attempt $$((attempt + 1))/3)"; \
		sleep $$delay; \
		attempt=$$((attempt + 1)); \
	done

show-data:
	find data -maxdepth 4 -type f | sort

dbt-debug:
	uvx --from dbt-bigquery dbt --project-dir $(DBT_DIR) --profiles-dir $(DBT_PROFILES_DIR) debug

dbt-build:
	uvx --from dbt-bigquery dbt --project-dir $(DBT_DIR) --profiles-dir $(DBT_PROFILES_DIR) build --vars '$(DBT_VARS)'

dbt-run:
	uvx --from dbt-bigquery dbt --project-dir $(DBT_DIR) --profiles-dir $(DBT_PROFILES_DIR) run --vars '$(DBT_VARS)'

dbt-test:
	uvx --from dbt-bigquery dbt --project-dir $(DBT_DIR) --profiles-dir $(DBT_PROFILES_DIR) test --vars '$(DBT_VARS)'

bigquery-bootstrap:
	@test -n "$(BQ_PROJECT)" || (echo "Set BQ_PROJECT=<gcp-project-id>"; exit 1)
	uv run python -m domus_dweller.sinks.bigquery_bootstrap --project "$(BQ_PROJECT)" --dataset "$(BQ_DATASET)" --location "$(BQ_LOCATION)"

daily-olx-bigquery-rent:
	@test -n "$(BQ_PROJECT)" || (echo "Set BQ_PROJECT=<gcp-project-id>"; exit 1)
	uv run python -m domus_dweller.sources.olx.ingest_bigquery --mode rent --project "$(BQ_PROJECT)" --dataset "$(BQ_DATASET)" --pages $(PAGES) --cities $(CITIES) --property-types-rent $(PROPERTY_TYPES_RENT)

daily-olx-bigquery-sale:
	@test -n "$(BQ_PROJECT)" || (echo "Set BQ_PROJECT=<gcp-project-id>"; exit 1)
	uv run python -m domus_dweller.sources.olx.ingest_bigquery --mode sale --project "$(BQ_PROJECT)" --dataset "$(BQ_DATASET)" --pages $(PAGES) --cities $(CITIES) --property-types-sale $(PROPERTY_TYPES_SALE)

daily-olx-bigquery: daily-olx-bigquery-rent daily-olx-bigquery-sale
