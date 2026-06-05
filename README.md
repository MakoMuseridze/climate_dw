# Global Climate Data Warehouse

> Integrating environmental and socioeconomic data for climate-trend analysis, on **ClickHouse**.

A full analytical data warehouse that unifies **15 authoritative global datasets** — temperature, CO₂ & greenhouse-gas emissions, energy, agriculture, natural disasters, sea level, and socioeconomic development — into a single ClickHouse star schema, queryable with sub-second cross-domain analytics and visualised in Grafana. Extractors are implemented for 17 sources; 15 are loaded and verified (see [Results](#results)).

Bachelor's project — Mako Museridze · Supervisor: Ana Margvelashvili.

---

## What's inside

| Layer | What | Where |
|-------|------|-------|
| **Schema** | 6 dimensions + 12 fact tables (star schema) | `sql/ddl/` |
| **Materialized views** | 5 incremental + 1 refreshable | `sql/ddl/03_materialized_views.sql` |
| **Dictionaries** | `dictGet` lookups for country/indicator/disaster | `sql/ddl/04_dictionaries.sql` |
| **ETL** | Download → parse → harmonize → load; extractors for 17 sources (15 loaded) | `etl/real/` |
| **Analytics** | 12 cross-domain queries (<2 s) + dictionary examples | `sql/queries/` |
| **Data quality** | 11 automated checks → audit table | `etl/dq.py` |
| **Dashboards** | Grafana, 9 panels across 6 themes | `dashboards/grafana/` |
| **Deployment** | Docker (ClickHouse 24.8 + Grafana 11) | `docker-compose.yml` |
| **Self-test** | Offline end-to-end validation (embedded ClickHouse) | `scripts/validate_local.py` |

Six themes: **atmospheric observations · GHG emissions · energy · agriculture & land use · natural disasters · socioeconomic development.**

---

## Quickstart

Requires **Docker** + Docker Compose and **Python 3.11+**. Five steps from a clean machine to a live dashboard:

```bash
# 1. Clone
git clone https://github.com/MakoMuseridze/climate_dw.git
cd climate_dw

# 2. Python deps (for ETL)
make install

# 3. Start ClickHouse + Grafana
make up

# 4. Create schema + reference data + load the registration-free public sources
make bootstrap        # = init-schema + seed + load-quick
make dq               # run the data-quality suite

# 5. Open Grafana → http://localhost:3000  (dashboard "Global Climate Data Warehouse — Overview")
```

That gives you a populated, queryable warehouse from the auto-downloading sources. To add the remaining sources (registration-gated or multi-GB), see [Loading the real sources](#loading-the-real-sources) below.

No Docker handy? Run the **offline self-test** — it stands up the whole schema in an embedded ClickHouse, loads a representative fixture, and runs every query + DQ check:

```bash
make validate
```

---

## Loading the real sources

```bash
make load-quick     # OWID CO2, OWID Energy, World Bank WDI, NOAA Mauna Loa, NASA GISTEMP — auto-download
make load-file      # GCB, ND-GAIN, EM-DAT, EDGAR, FAOSTAT, Climate TRACE, Forest Watch — see below
make load-gridded   # HadCRUT5, NOAAGlobalTemp, GPCC, ERA5 — heavy / gated
make load-all       # everything available
```

Some sources are behind a registration form or are multi-GB, so you download them once and drop the file in `data/raw/` (the extractor finds it). The console prints exactly what it expects:

| Source | Action | Get it from |
|--------|--------|-------------|
| EM-DAT | register, export xlsx → `data/raw/` | https://public.emdat.be/ |
| ERA5 | CDS account + `~/.cdsapirc`; `cdsapi` auto-downloads | https://cds.climate.copernicus.eu/ |
| ND-GAIN | download zip → `data/raw/` | https://gain.nd.edu/our-work/country-index/download-data/ |
| Global Carbon Budget | download xlsx → `data/raw/` | https://globalcarbonbudget.org/ |
| EDGAR / FAOSTAT / CHIRPS / GFW | download → `data/raw/` | see `etl/sources.py` |

See `docs/installation.md` for the full per-source guide.

---

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — design, star-schema + data-flow + deployment diagrams, ClickHouse engine choices
- [`docs/data_dictionary.md`](docs/data_dictionary.md) — every table and column
- [`docs/installation.md`](docs/installation.md) — setup + per-source download guide + troubleshooting
- [`docs/query_reference.md`](docs/query_reference.md) — ETL CLI, ClickHouse endpoints, and the analytical query library
- [`docs/user_guide.md`](docs/user_guide.md) — worked use cases and Grafana walkthrough
- [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`LICENSE`](LICENSE) (MIT)

---

## Project layout

```
climate_dw/
├─ sql/ddl/            schema: dimensions, facts, materialized views, dictionaries, audit
├─ sql/queries/        analytical query library + dictionary examples
├─ etl/                Python ETL
│  ├─ real/            one extractor per source (download → parse → harmonize → load)
│  ├─ dimensions.py    canonical reference data (countries, indicators, sectors, ...)
│  ├─ run_etl.py       orchestrator (CLI)
│  └─ dq.py            data-quality suite
├─ dashboards/grafana/ provisioned datasource + dashboard
├─ docker-compose.yml  ClickHouse 24.8 + Grafana 11
├─ scripts/validate_local.py   offline end-to-end self-test
├─ docs/               architecture, data dictionary, installation, query reference, user guide
├─ CONTRIBUTING.md     dev setup + how to add a data source
└─ LICENSE             MIT
```

## Results

Verified on the production warehouse (real data, ClickHouse 24.8):

| Metric | Proposal target | Achieved |
|--------|-----------------|----------|
| Data sources loaded | ≥ 15 | **15** |
| Total fact rows | ≥ 500,000 | **3,340,211** |
| Fact tables / dimensions | ≥ 8 / ≥ 3 | **12 / 6** |
| Materialized views | ≥ 5 (incremental + refreshable) | **6** (5 incremental + 1 refreshable) |
| Analytical queries < 2 s | ≥ 10 | **12** |
| Grafana panels / themes | ≥ 8 / 6 | **9 / 6** |
| Data-quality checks passing | ≥ 95% | **11 / 11 (100%)** |

A standout cross-source check: OWID and the Global Carbon Budget independently agree on global CO₂ to within **0.02%**.

**No Docker or downloads?** `make validate` stands up the whole schema in an embedded ClickHouse, loads the offline test fixture, and runs every query + DQ check end-to-end (~900k fixture rows, 12/12 queries < 2 s, 11/11 checks pass) — exercising the identical SQL the production warehouse uses.
