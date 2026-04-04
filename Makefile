.PHONY: lint test ci daily-olx-rent daily-olx-sale daily-olx show-data

COV_MIN := 70
UA := Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36
OLX_SALE_URL := https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/krakow/
OLX_RENT_URL := https://www.olx.pl/nieruchomosci/mieszkania/wynajem/krakow/
PAGES ?= 5
DATE ?= $(shell date +%F)

lint:
	uv run ruff check .

test:
	uv run pytest --cov=domus_dweller --cov-report=term-missing --cov-fail-under=$(COV_MIN)

ci: lint test

daily-olx-rent:
	mkdir -p data/raw/$(DATE) data/parsed/$(DATE)
	set -e; for i in $$(seq 1 $(PAGES)); do \
		curl -L -A "$(UA)" -o data/raw/$(DATE)/olx_rent_page_$$i.html "$(OLX_RENT_URL)?page=$$i"; \
		uv run python -m domus_dweller.parse --source olx --input data/raw/$(DATE)/olx_rent_page_$$i.html --output data/parsed/$(DATE)/olx_rent_page_$$i.json; \
	done
	uv run python -m domus_dweller.merge_pages --pattern "data/parsed/$(DATE)/olx_rent_page_*.json" --output data/parsed/$(DATE)/olx_rent_all.json

daily-olx-sale:
	mkdir -p data/raw/$(DATE) data/parsed/$(DATE)
	set -e; for i in $$(seq 1 $(PAGES)); do \
		curl -L -A "$(UA)" -o data/raw/$(DATE)/olx_sale_page_$$i.html "$(OLX_SALE_URL)?page=$$i"; \
		uv run python -m domus_dweller.parse --source olx --input data/raw/$(DATE)/olx_sale_page_$$i.html --output data/parsed/$(DATE)/olx_sale_page_$$i.json; \
	done
	uv run python -m domus_dweller.merge_pages --pattern "data/parsed/$(DATE)/olx_sale_page_*.json" --output data/parsed/$(DATE)/olx_sale_all.json

daily-olx: daily-olx-rent daily-olx-sale

show-data:
	find data -maxdepth 4 -type f | sort
