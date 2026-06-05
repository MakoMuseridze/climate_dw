# Architecture

## Overview

The warehouse is a **star schema** on ClickHouse: conformed dimensions at the centre of many fact tables, one fact table per measurement grain/theme. Source data is heterogeneous (CSV, Excel, NetCDF, GeoTIFF, API; daily/monthly/annual; station/gridded/country), so the ETL layer harmonizes everything to a common country + time grain before loading.

```
 Sources (15 loaded)     ETL (Python)                 ClickHouse                Presentation
┌────────────┐   download   ┌──────────────┐  insert  ┌────────────────┐       ┌──────────┐
│ OWID, WDI, │ ───────────▶ │ extract →    │ ───────▶ │ dim_* (6)      │       │ Grafana  │
│ NOAA, NASA,│              │ parse →      │          │ fact_* (12)    │ ────▶ │ 9 panels │
│ EM-DAT,    │   ISO3        │ harmonize →  │          │ MVs (6)        │       │ 6 themes │
│ ERA5, GPCC,│   country_id  │ load + log   │          │ dictionaries   │       └──────────┘
│ EDGAR, ... │ ───────────▶ │ lineage      │          │ dq_audit_log   │
└────────────┘              └──────────────┘          └────────────────┘
```

## Data flow

```mermaid
flowchart LR
    subgraph SRC[15 loaded sources]
      A1[CSV / TXT\nOWID, GISTEMP, NOAA]
      A2[API\nWorld Bank WDI]
      A3[Excel\nEM-DAT, EDGAR, GCB]
      A4[NetCDF / GeoTIFF\nERA5, HadCRUT5, GPCC, CHIRPS]
    end
    SRC --> EX[Extractors\netl/real/*]
    EX --> HARM[Harmonize\nISO3 -> country_id\nunits, grain]
    HARM --> LOAD[Loader\nclickhouse-connect]
    LOAD --> FACTS[(fact_* tables)]
    LOAD --> LIN[(meta_load_lineage)]
    FACTS --> MV[Materialized views\nincremental + refreshable]
    DIM[(dim_* tables)] --> DICT[Dictionaries]
    FACTS --> Q[Analytical queries]
    DIM --> Q
    MV --> Q
    DICT --> Q
    Q --> G[Grafana]
    FACTS --> DQ[DQ suite] --> AUD[(dq_audit_log)]
```

## Star schema

```mermaid
erDiagram
    dim_country ||--o{ fact_emissions_co2 : country_id
    dim_country ||--o{ fact_energy : country_id
    dim_country ||--o{ fact_temperature : country_id
    dim_country ||--o{ fact_disasters : country_id
    dim_country ||--o{ fact_socioeconomic : country_id
    dim_country ||--o{ fact_vulnerability : country_id
    dim_country ||--o{ fact_agriculture : country_id
    dim_indicator ||--o{ fact_socioeconomic : indicator_id
    dim_disaster_type ||--o{ fact_disasters : disaster_type_id
    dim_sector ||--o{ fact_emissions_by_sector : sector_id
    dim_source ||--o{ fact_emissions_co2 : source_id
    dim_date ||--o{ fact_temperature : date

    dim_country {
        UInt16 country_id PK
        FixedString iso3
        String country_name
        LowCardinality income_group
        LowCardinality region
        Date32 valid_from "SCD2"
    }
    fact_emissions_co2 {
        UInt16 country_id FK
        UInt16 year
        Float64 co2_mt
        Float64 co2_per_capita_t
        UInt16 source_id FK
    }
    fact_socioeconomic {
        UInt16 country_id FK
        UInt32 indicator_id FK
        UInt16 year
        Float64 value
    }
```

The full table inventory is in [`data_dictionary.md`](data_dictionary.md).

## Deployment

The runtime is two Docker containers plus the ETL process on the host. ClickHouse
holds the warehouse; Grafana queries it live over HTTP; the Python ETL connects
from the host to load data and run the quality suite.

```mermaid
flowchart LR
    subgraph HOST[Host machine]
      ETL["Python ETL\netl/run_etl.py · etl/dq.py"]
      RAW[("data/raw/\ndownloaded sources")]
    end
    subgraph DOCKER[Docker Compose]
      CH["ClickHouse 24.8\n:8123 HTTP · :9000 native\nvolume: ch_data"]
      GRAF["Grafana 11\n:3000\nprovisioned datasource + dashboard"]
    end
    RAW --> ETL
    ETL -- "clickhouse-connect (insert/query)" --> CH
    GRAF -- "live SQL over HTTP" --> CH
    USER["Browser / clickhouse-client / BI"] --> GRAF
    USER --> CH
```

Configuration lives in `docker-compose.yml` (services, ports, volume) and
`docker/clickhouse/users.d/` (user + experimental settings, incl. refreshable
materialized views). ClickHouse data persists in a named Docker volume, so the
warehouse survives `make down` / `make up`.

## ClickHouse design decisions

**Engines.** Facts use `ReplacingMergeTree(_inserted_at)` so re-running an ETL load is idempotent — the newest insert for a key wins after merges. Dimensions use `ReplacingMergeTree(_version)`. Aggregated MV targets use `SummingMergeTree` (additive rollups: emissions/disaster counts by decade) and `AggregatingMergeTree` (mergeable states: average temperature anomaly, average CO₂ ppm).

**Sort keys / partitioning.** `ORDER BY` leads with the most selective filter columns (usually `country_id`, then time). Annual facts are partitioned by **decade** (`intDiv(year,10)*10`), monthly facts by decade-of-year — a deliberate choice to keep the partition count small (~15) while still enabling partition pruning on time-range queries.

**Multi-source coexistence.** Facts that legitimately receive more than one source (CO₂ from OWID + Global Carbon Budget; temperature from GISTEMP + HadCRUT5 + ERA5; precipitation from GPCC + CHIRPS) include `source_id` **in the sort key**, so the sources coexist rather than overwrite. This is what powers the cross-source **reconciliation** data-quality check (OWID vs GCB).

**Date range.** ClickHouse `Date` only covers 1970–2149; climate series reach back to the 19th century and the SCD2 sentinel is far in the future, so all date columns use **`Date32`** (1900–2299) and pre-1900 records are clipped at load.

**Dictionaries.** `dim_country`, `dim_indicator`, and `dim_disaster_type` are exposed as in-memory `HASHED()` dictionaries, so hot lookups (income group, region, indicator name) use `dictGet` instead of a JOIN — keeping wide analytical queries sub-second.

**Materialized views.** Five incremental MVs pre-aggregate on insert (decade emissions, annual temperature, annual CO₂, disasters by type/decade, annual energy mix). One **refreshable** MV (`mv_country_year_overview`) rebuilds a wide denormalized country-year table on a schedule by JOINing four facts — the workhorse behind several dashboard panels.

## Lineage & data quality

Every fact row carries `source_id` → `dim_source`. Each load run appends to `meta_load_lineage` (rows loaded, timing, status, access date). The DQ suite (`etl/dq.py`) runs 11 checks across five categories — completeness, referential integrity, range, uniqueness, cross-source reconciliation — and logs each result with pass/fail vs. threshold to `dq_audit_log`.
