# Query & Interface Reference

This warehouse has no bespoke REST layer — it is consumed through three
interfaces: the **ETL command-line interface**, the **ClickHouse query
endpoints** (HTTP and native), and a curated **analytical query library**
(plus dictionary-accelerated variants). This document is the reference for all
three: parameters, usage examples, expected responses, and error handling.

---

## 1. ETL command-line interface

All ingestion runs through one orchestrator, `python -m etl.run_etl`
(the `make` targets are thin wrappers around it).

| Argument | Parameter | Description |
|----------|-----------|-------------|
| `--init-schema` | – | Create database, tables, materialized views, dictionaries. |
| `--seed` | – | Load dimension / reference data (countries, indicators, sectors, sources, calendar). |
| `--bootstrap` | – | `--init-schema` + `--seed` + load the `quick` group. |
| `--group` | `quick` \| `file` \| `gridded` \| `all` | Load a predefined group of sources. |
| `--sources` | `<name> [<name> ...]` | Load specific sources by key (see `--list`). |
| `--all` | – | Load every registered source. |
| `--dry-run` | – | Extract + parse + preview the first rows; do **not** load. |
| `--list` | – | Print all known source keys and group memberships. |

**Examples**

```bash
python -m etl.run_etl --bootstrap                 # fastest path to a populated DW
python -m etl.run_etl --sources owid_co2 wdi      # load two specific sources
python -m etl.run_etl --group file                # load file-based sources in data/raw/
python -m etl.run_etl --group quick --dry-run     # preview without loading
python -m etl.run_etl --list                      # discover source keys
```

**Response.** Each run prints a per-source table (`source`, `rows`, `status`)
and a loaded-row total. Every load also appends a row to
`climate.meta_load_lineage` (rows loaded, timing, status, access date, checksum).

**Error handling.** A failing source is isolated — it prints
`FAIL: <reason>` and is logged to lineage with status `FAILED`, while the other
sources in the run continue. Set `ETL_DEBUG=1` to print a full traceback.
Common statuses:

| Message | Meaning | Action |
|---------|---------|--------|
| `needs a manual download` | A file-based source has no file in `data/raw/`. | Download it; see `docs/installation.md`. |
| `N unmatched labels` | Some rows had country labels with no ISO3 match (regional aggregates like "World"/"EU"). | Expected — those rows are skipped. |
| `Connection refused` | ClickHouse is not up. | `make up`, wait for healthy (`make ps`). |

---

## 2. ClickHouse query endpoints

`make up` exposes ClickHouse on two ports (defaults; override with the
`CH_HOST` / `CH_PORT` / `CH_USER` / `CH_PASS` environment variables):

| Interface | Port | Use |
|-----------|------|-----|
| HTTP | `8123` | `curl`, BI tools, Grafana, quick scripts |
| Native TCP | `9000` | `clickhouse-client`, high-throughput drivers |

Connection defaults: `host=localhost`, `user=default`, `password=climate`,
`database=climate` (the password is set by the bundled compose file; override
any of these with `CH_HOST` / `CH_PORT` / `CH_USER` / `CH_PASS`).

**HTTP example**

```bash
curl 'http://localhost:8123/?database=climate' --user 'default:climate' \
     --data-binary "SELECT count() FROM fact_emissions_co2 FORMAT JSON"
```

The HTTP endpoint returns standard HTTP status codes: `200` on success,
`400`/`500` with a ClickHouse error message in the body on a bad query,
`516` on authentication failure.

**Native client**

```bash
docker compose exec clickhouse clickhouse-client --password climate --database climate \
  --query "SELECT count(DISTINCT source_id) FROM meta_load_lineage WHERE status='SUCCESS'"
```

**Python**

```python
import clickhouse_connect
client = clickhouse_connect.get_client(host="localhost", database="climate", password="climate")
df = client.query_df("SELECT * FROM agg_temp_annual WHERE country_id = 0")
```

---

## 3. Analytical query library

`sql/queries/analytical_queries.sql` — 12 cross-domain queries spanning all six
themes, each targeting < 2 s on the full warehouse. By convention, CO₂ queries
filter `source_id = 1` (OWID) as the canonical series.

| # | Title | Theme(s) | Reads |
|---|-------|----------|-------|
| Q1 | Emissions vs GDP correlation (latest full year) | Emissions × Socioeconomic | `fact_emissions_co2`, `fact_socioeconomic` |
| Q2 | Top 15 cumulative CO₂ emitters (historical responsibility) | Emissions | `fact_emissions_co2`, `dim_country` |
| Q3 | Disaster frequency & deaths by income group and decade | Disasters × Socioeconomic | `agg_disasters_by_type_decade` (MV), `dim_country` |
| Q4 | Renewable-energy transition by region over time | Energy | `fact_energy`, `dim_country` |
| Q5 | Global temperature anomaly vs atmospheric CO₂ | Atmospheric | `agg_temp_annual` + `agg_co2_annual` (MVs) |
| Q6 | CO₂ per capita by income group over time | Emissions × Socioeconomic | `fact_emissions_co2`, `dim_country` |
| Q7 | Decoupling: GDP growth vs emissions change, 2000→2020 | Emissions × Socioeconomic | `fact_emissions_co2`, `fact_socioeconomic` |
| Q8 | Disaster damage vs climate vulnerability (ND-GAIN) | Disasters × Vulnerability | `fact_disasters`, `fact_vulnerability` |
| Q9 | Renewable-transition leaders (largest share gain) | Energy | `fact_energy`, `dim_country` |
| Q10 | Carbon intensity of the economy by region, decade | Emissions × Socioeconomic | `fact_emissions_co2`, `dim_country` |
| Q11 | Sea-level rise rate per decade | Ocean / Atmospheric | `fact_sea_level` |
| Q12 | Agriculture production vs agricultural emissions | Agriculture × Emissions | `fact_agriculture`, `fact_emissions_by_sector` |

**Run the whole library with timings** (offline, no server):

```bash
make validate
```

**Run a single query** against the live warehouse:

```bash
docker compose exec -T clickhouse clickhouse-client --password climate --database climate \
  --multiquery < sql/queries/analytical_queries.sql
```

---

## 4. Dictionary functions (`dictGet`)

`dim_country`, `dim_indicator`, and `dim_disaster_type` are also exposed as
in-memory `HASHED()` dictionaries (`sql/ddl/04_dictionaries.sql`), so hot
lookups replace a JOIN with an O(1) `dictGet`. Examples live in
`sql/queries/dictionary_examples.sql`:

```sql
SELECT dictGet('climate.dict_country', 'income_group', toUInt64(country_id)) AS income_group,
       round(avg(co2_per_capita_t), 2) AS avg_co2_per_capita_t
FROM climate.fact_emissions_co2
WHERE source_id = 1 AND year = 2020
GROUP BY income_group
ORDER BY avg_co2_per_capita_t DESC;
```

Dictionaries require a running ClickHouse server (they are not part of the
embedded `make validate` fixture, which uses explicit JOINs).

---

## 5. Data-quality interface

```bash
make dq        # runs etl/dq.py against the live warehouse
```

Runs 11 checks across five categories (completeness, referential integrity,
range, uniqueness, cross-source reconciliation), prints a pass/fail scorecard,
and logs every result to `climate.dq_audit_log` with the metric value,
threshold, comparator, and status. Inspect history with:

```sql
SELECT check_name, check_category, metric_value, threshold, status
FROM climate.dq_audit_log
WHERE run_ts = (SELECT max(run_ts) FROM climate.dq_audit_log)
ORDER BY check_category;
```
