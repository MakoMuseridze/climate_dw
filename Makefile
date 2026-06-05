# ============================================================
# Global Climate Data Warehouse — task runner
# ============================================================
.DEFAULT_GOAL := help
PY := python3

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## install Python dependencies
	$(PY) -m pip install -r requirements.txt

up:  ## start ClickHouse + Grafana (Docker)
	docker compose up -d

down:  ## stop the stack
	docker compose down

ps:  ## show container status
	docker compose ps

logs:  ## tail ClickHouse logs
	docker compose logs -f clickhouse

init-schema:  ## create database, tables, MVs, dictionaries
	$(PY) -m etl.run_etl --init-schema

seed:  ## load dimension / reference data
	$(PY) -m etl.run_etl --seed

load-quick:  ## load registration-free public sources (OWID, WDI, NOAA, GISTEMP)
	$(PY) -m etl.run_etl --group quick

load-file:  ## load file-based sources you've placed in data/raw (GCB, ND-GAIN, EM-DAT, EDGAR, FAOSTAT, ...)
	$(PY) -m etl.run_etl --group file

load-gridded:  ## load gridded NetCDF/ERA5 sources (heavy; on your machine)
	$(PY) -m etl.run_etl --group gridded

load-all:  ## load every available source
	$(PY) -m etl.run_etl --all

bootstrap:  ## init-schema + seed + load quick sources (fastest path to a populated DW)
	$(PY) -m etl.run_etl --bootstrap

dq:  ## run the data-quality suite (logs to climate.dq_audit_log)
	$(PY) -m etl.dq

validate:  ## offline self-test (embedded ClickHouse): schema + fixture + queries + DQ
	$(PY) scripts/validate_local.py

list-sources:  ## list known sources and groups
	$(PY) -m etl.run_etl --list

clean:  ## remove cached downloads and staging
	rm -rf data/raw/* data/staging/* && touch data/raw/.gitkeep data/staging/.gitkeep

.PHONY: help install up down ps logs init-schema seed load-quick load-file load-gridded load-all bootstrap dq validate list-sources clean
