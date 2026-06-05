# Installation & Operations Guide

## Prerequisites

- **Docker** + Docker Compose (for ClickHouse + Grafana), or an existing ClickHouse 24.x server
- **Python 3.11+**
- ~5 GB free disk for raw downloads + ClickHouse data (more if you load the gridded NetCDF sources)

## Windows (without `make`)

`make` isn't installed on Windows by default, and the offline self-test (`make validate`) needs `chdb`, which is Linux/macOS-only. Everything else works the same — each `make` target is just a shortcut. Run the command on the right in PowerShell (or install make with `winget install GnuWin32.Make`):

| `make` target | Windows command |
|---|---|
| `make install` | `pip install -r requirements.txt` |
| `make up` / `make down` | `docker compose up -d` / `docker compose down` |
| `make ps` | `docker compose ps` |
| `make bootstrap` | `python -m etl.run_etl --bootstrap` |
| `make load-quick` / `load-file` / `load-gridded` | `python -m etl.run_etl --group quick` (or `file` / `gridded`) |
| `make dq` | `python -m etl.dq` |
| `make export` | `python -m etl.export_warehouse` (add `--public` to drop restricted sources) |
| `make restore` | `python -m etl.restore_warehouse` |
| `make list-sources` | `python -m etl.run_etl --list` |

ClickHouse + Grafana still run via Docker Desktop (Windows-supported); only the `chdb` self-test is unavailable on Windows.

## 1. Python environment

```bash
cd climate_dw
python -m venv .venv && source .venv/bin/activate    # optional
make install                                         # pip install -r requirements.txt
```

## 2. Start the stack

```bash
make up        # docker compose up -d  (ClickHouse :8123/:9000, Grafana :3000)
make ps        # check health
```

ClickHouse connection defaults (override with env vars `CH_HOST`, `CH_PORT`, `CH_USER`, `CH_PASS`):

```
host=localhost  port=8123 (HTTP)  user=default  password=climate  database=climate
```

(The password `climate` is set by the bundled `docker-compose.yml` and `docker/clickhouse/users.d/default-user.xml`; the ETL reads it from `CH_PASS`, defaulting to the same value, so `make` targets work with no extra setup.)

The bundled `docker/clickhouse/users.d/settings.xml` enables refreshable materialized views (experimental in 24.x).

## 3. Build the warehouse

```bash
make init-schema   # CREATE DATABASE + tables + MVs + dictionaries
make seed          # load dimensions / reference data (countries, indicators, sectors, sources, calendar)
make load-quick    # download + load the registration-free public sources
make dq            # run the data-quality suite
```

Or all three of the first steps at once:

```bash
make bootstrap     # init-schema + seed + load-quick
```

## 4. Loading each source

`make load-quick` fully automates the registration-free sources:

| Source | Target table | Notes |
|--------|--------------|-------|
| OWID CO2 | `fact_emissions_co2` | auto-download CSV |
| OWID Energy | `fact_energy` | auto-download CSV |
| World Bank WDI | `fact_socioeconomic` | 25 indicators via API (cached to `data/raw/wdi_socioeconomic.parquet`) |
| NOAA Mauna Loa | `fact_co2_atmospheric` | auto-download TXT |
| NASA GISTEMP | `fact_temperature` (global) | auto-download CSV |

File-based sources — download once, drop in `data/raw/`, then `make load-file`:

| Source | Target | Download | Place in data/raw as |
|--------|--------|----------|----------------------|
| Global Carbon Budget | `fact_emissions_co2` (source 8) | https://globalcarbonbudget.org/ | `*National_Fossil*.xlsx` |
| ND-GAIN | `fact_vulnerability` | https://gain.nd.edu/our-work/country-index/download-data/ | `resources.zip` |
| EM-DAT *(register)* | `fact_disasters` | https://public.emdat.be/ | `*emdat*.xlsx` |
| EDGAR v8.0 | `fact_emissions_by_sector` | https://edgar.jrc.ec.europa.eu/dataset_ghg80 | `*EDGAR*.xlsx` |
| FAOSTAT | `fact_agriculture` | https://bulks-faostat.fao.org/production/ | `*FAOSTAT*.csv` or `.zip` |
| CSIRO sea level | `fact_sea_level` | https://www.cmar.csiro.au/sealevel/ | `*gmsl*.txt` |
| Climate TRACE | `fact_emissions_by_sector` | https://climatetrace.org/data | `*climatetrace*.csv` |
| Global Forest Watch | `fact_agriculture` | https://www.globalforestwatch.org/ | `*gfw*loss*.csv` |

Gridded + gated sources (heavy; `make load-gridded`):

| Source | Target | Setup |
|--------|--------|-------|
| ERA5 | `fact_temperature` | CDS account + `~/.cdsapirc`; `cdsapi` auto-downloads (may queue for hours) |
| HadCRUT5 | `fact_temperature` | download `.nc` → `data/raw/` |
| NOAAGlobalTemp | `fact_temperature` | download `.nc` → `data/raw/` |
| GPCC | `fact_precipitation` | download `.nc` → `data/raw/` |

Run a single source, or preview without loading:

```bash
python -m etl.run_etl --sources owid_co2 wdi
python -m etl.run_etl --group quick --dry-run     # extract + show a preview, don't load
python -m etl.run_etl --list                      # list sources & groups
```

Every load is idempotent (ReplacingMergeTree) — re-running re-loads cleanly. Each run appends to `climate.meta_load_lineage`.

## 5. Grafana

Open http://localhost:3000 (anonymous admin enabled for local dev). The **ClickHouse** datasource and the **Global Climate Data Warehouse — Overview** dashboard are auto-provisioned. If a panel shows no data, confirm the datasource is connected and the relevant source has been loaded.

## 6. Offline self-test (no Docker, no network)

```bash
make validate    # embedded ClickHouse: schema + ~900k-row fixture + all queries + DQ
```

## Troubleshooting

- **`Connection refused`** — ClickHouse not up yet; `make ps` and wait for healthy.
- **Refreshable MV error on init** — ensure the stack was started with the bundled `users.d` settings (`make up`), or set `allow_experimental_refreshable_materialized_view=1` server-side.
- **`needs a manual download`** — a file-based source has no file in `data/raw/`; see the table above.
- **Unmatched countries** — the loader reports any country labels it couldn't map to ISO3; these rows are skipped (aggregates like "World"/"EU" are intentionally excluded).
