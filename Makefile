.PHONY: lint test data verify daily-olx-rent daily-olx-sale daily-olx daily-olx-parse daily-olx-enrich daily-olx-sink-motherduck motherduck-bootstrap silver-sync

COV_MIN := 90
UA := Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36
OLX_BASE_URL := https://www.olx.pl/nieruchomosci
FETCH_FLAGS := --fail --silent --show-error --location --retry 3 --retry-delay 2 --connect-timeout 10 --max-time 45
MD_DATABASE ?= my_db
# Approximate 30 km coverage around Krakow, configurable per run:
# make daily-olx CITIES="krakow wieliczka skawina"
CITIES ?= krakow wieliczka skawina niepolomice zabierzow zielonki swiatniki-gorne
# "All non-commercial housing types" in OLX categories for v1:
PROPERTY_TYPES_RENT ?= mieszkania domy pokoje
PROPERTY_TYPES_SALE ?= mieszkania domy
PAGES ?= 30
DATE ?= $(shell date +%F)
lint:
	uv run ruff check .

test:
	uv run pytest --cov=domus_dweller --cov-report=term-missing --cov-fail-under=$(COV_MIN)

data:
	cd transform && uv run dbt test --target prod

verify: lint test

WORKERS ?= 4

daily-olx-rent:
	uv run python -m domus_dweller.sources.olx.orchestrator --mode rent --date "$(DATE)" --pages "$(PAGES)" --cities "$(CITIES)" --workers "$(WORKERS)"

daily-olx-sale:
	uv run python -m domus_dweller.sources.olx.orchestrator --mode sale --date "$(DATE)" --pages "$(PAGES)" --cities "$(CITIES)" --workers "$(WORKERS)"

daily-olx:
	uv run python -m domus_dweller.sources.olx.orchestrator --mode both --date "$(DATE)" --pages "$(PAGES)" --cities "$(CITIES)" --workers "$(WORKERS)"

daily-olx-parse: daily-olx

daily-olx-enrich:
	uv run python -m domus_dweller.sources.olx.enrich \
		--input data/parsed/$(DATE)/olx_rent_all.json \
		--output data/parsed/$(DATE)/olx_rent_all.json \
		--mode rent \
		--only-new \
		--database "$(MD_DATABASE)"
	uv run python -m domus_dweller.sources.olx.enrich \
		--input data/parsed/$(DATE)/olx_sale_all.json \
		--output data/parsed/$(DATE)/olx_sale_all.json \
		--mode sale \
		--only-new \
		--database "$(MD_DATABASE)"

daily-olx-sink-motherduck:
	@attempt=1; \
	until uv run python -m domus_dweller.sinks.olx_files_to_motherduck --mode both --database "$(MD_DATABASE)" --date "$(DATE)"; do \
		if [ $$attempt -ge 3 ]; then \
			echo "MotherDuck sink failed after $$attempt attempts"; \
			exit 1; \
		fi; \
		delay=$$((attempt * 10)); \
		echo "Retrying sink in $$delay seconds (attempt $$((attempt + 1))/3)"; \
		sleep $$delay; \
		attempt=$$((attempt + 1)); \
	done

motherduck-bootstrap:
	uv run python -m domus_dweller.sinks.motherduck_bootstrap --database "$(MD_DATABASE)"

silver-sync:
	cd transform && uv run dbt deps && uv run dbt build --target prod
