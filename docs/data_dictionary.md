# Data Dictionary

Authoritative listing generated from the ClickHouse schema (`system.columns`). Meta columns `_inserted_at` / `_version` (load bookkeeping) are omitted.

ClickHouse objects: **27 tables** + 6 materialized views + 3 dictionaries.

## Dimensions

### `dim_country`
_Conformed country dimension (SCD2-capable)_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 | Surrogate key |
| `iso3` | FixedString(3) | ISO 3166-1 alpha-3 (e.g. USA, GEO) |
| `iso2` | FixedString(2) | ISO 3166-1 alpha-2 |
| `country_name` | String |  |
| `region` | LowCardinality(String) | World Bank region |
| `subregion` | LowCardinality(String) |  |
| `continent` | LowCardinality(String) |  |
| `income_group` | LowCardinality(String) | WB: Low / Lower-middle / Upper-middle / High |
| `un_member` | UInt8 |  |
| `area_km2` | Float64 |  |
| `valid_from` | Date32 |  |
| `valid_to` | Date32 |  |
| `is_current` | UInt8 |  |

### `dim_date`
_Calendar dimension_

| Column | Type | Description |
|--------|------|-------------|
| `date` | Date32 |  |
| `year` | UInt16 |  |
| `month` | UInt8 |  |
| `day` | UInt8 |  |
| `quarter` | UInt8 |  |
| `decade` | UInt16 |  |
| `day_of_year` | UInt16 |  |
| `month_name` | LowCardinality(String) |  |
| `is_year_start` | UInt8 |  |
| `is_month_start` | UInt8 |  |

### `dim_disaster_type`
_EM-DAT disaster type hierarchy_

| Column | Type | Description |
|--------|------|-------------|
| `disaster_type_id` | UInt16 |  |
| `disaster_group` | LowCardinality(String) | Natural / Technological |
| `disaster_subgroup` | LowCardinality(String) | Geophysical / Meteorological / Hydrological / Climatological / Biological |
| `disaster_type` | LowCardinality(String) | Flood / Storm / Drought / Earthquake / Wildfire ... |
| `disaster_subtype` | String |  |

### `dim_indicator`
_Indicator dimension for tall socioeconomic facts_

| Column | Type | Description |
|--------|------|-------------|
| `indicator_id` | UInt32 |  |
| `indicator_code` | String | e.g. NY.GDP.MKTP.CD |
| `indicator_name` | String |  |
| `unit` | LowCardinality(String) |  |
| `theme` | LowCardinality(String) |  |
| `source` | LowCardinality(String) |  |

### `dim_sector`
_Emissions sector dimension_

| Column | Type | Description |
|--------|------|-------------|
| `sector_id` | UInt16 |  |
| `sector_name` | LowCardinality(String) | Energy / Industry / Transport / Agriculture / Waste / Buildings |
| `ipcc_code` | String |  |

### `dim_source`
_Source registry (provenance)_

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | UInt16 |  |
| `source_name` | String |  |
| `domain` | LowCardinality(String) | Emissions / Energy / Temperature / Disasters / ... |
| `format` | LowCardinality(String) | CSV / Excel / NetCDF / API / TXT |
| `url` | String |  |
| `license` | String |  |
| `coverage` | String |  |

## Fact tables

### `fact_agriculture`
_Annual agriculture & land-use metrics by country_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `item` | LowCardinality(String) | e.g. Cereals, Forest land, Rice |
| `element` | LowCardinality(String) | e.g. Area harvested, Production |
| `value` | Float64 |  |
| `unit` | LowCardinality(String) |  |
| `source_id` | UInt16 |  |

### `fact_co2_atmospheric`
_Monthly atmospheric CO2 (ppm)_

| Column | Type | Description |
|--------|------|-------------|
| `date` | Date32 | Month start |
| `station` | LowCardinality(String) |  |
| `co2_ppm` | Float32 |  |
| `co2_trend_ppm` | Float32 |  |
| `source_id` | UInt16 |  |

### `fact_disasters`
_Annual natural-disaster impacts by country and type_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `disaster_type_id` | UInt16 |  |
| `events` | UInt32 |  |
| `total_deaths` | UInt64 |  |
| `total_affected` | UInt64 |  |
| `total_damage_usd_k` | Float64 | Total damage, thousands USD |
| `source_id` | UInt16 |  |

### `fact_emissions_by_sector`
_Annual emissions by sector and gas (EDGAR + Climate TRACE)_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `sector_id` | UInt16 |  |
| `gas` | LowCardinality(String) | CO2 / CH4 / N2O |
| `emissions_mt_co2e` | Float64 |  |
| `source_id` | UInt16 |  |

### `fact_emissions_co2`
_Annual CO2 emissions by country (OWID + GCB coexist via source_id)_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `co2_mt` | Float64 | Total CO2, million tonnes |
| `co2_per_capita_t` | Float64 |  |
| `co2_per_gdp_kg` | Float64 | kg CO2 per USD GDP |
| `coal_co2_mt` | Float64 |  |
| `oil_co2_mt` | Float64 |  |
| `gas_co2_mt` | Float64 |  |
| `cement_co2_mt` | Float64 |  |
| `cumulative_co2_mt` | Float64 |  |
| `share_global_co2` | Float32 |  |
| `source_id` | UInt16 |  |

### `fact_energy`
_Annual energy consumption and generation mix by country_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `primary_energy_twh` | Float64 |  |
| `fossil_share_pct` | Float32 |  |
| `renewables_share_pct` | Float32 |  |
| `nuclear_share_pct` | Float32 |  |
| `low_carbon_share_pct` | Float32 |  |
| `electricity_demand_twh` | Float64 |  |
| `energy_per_capita_kwh` | Float64 |  |
| `source_id` | UInt16 |  |

### `fact_ghg_emissions`
_Annual total greenhouse-gas emissions by country_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `ghg_total_mt_co2e` | Float64 |  |
| `ch4_mt_co2e` | Float64 |  |
| `n2o_mt_co2e` | Float64 |  |
| `ghg_per_capita_t` | Float64 |  |
| `source_id` | UInt16 |  |

### `fact_precipitation`
_Monthly precipitation by country (mm, GPCC + CHIRPS)_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `date` | Date32 | Month start |
| `precip_mm` | Float32 |  |
| `source_id` | UInt16 |  |

### `fact_sea_level`
_Global mean sea level (mm)_

| Column | Type | Description |
|--------|------|-------------|
| `date` | Date32 |  |
| `gmsl_mm` | Float32 | Global mean sea level vs baseline |
| `gmsl_uncertainty_mm` | Float32 |  |
| `source_id` | UInt16 |  |

### `fact_socioeconomic`
_Annual socioeconomic indicators (GDP, population, urbanization, etc.)_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `indicator_id` | UInt32 |  |
| `year` | UInt16 |  |
| `value` | Float64 |  |
| `source_id` | UInt16 |  |

### `fact_temperature`
_Monthly temperature anomaly (country_id 0 = global, multi-source)_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `date` | Date32 | Month start (YYYY-MM-01) |
| `temp_anomaly_c` | Float32 | Anomaly vs 1951-1980 baseline |
| `temp_abs_c` | Nullable(Float32) |  |
| `source_id` | UInt16 |  |

### `fact_vulnerability`
_Annual ND-GAIN climate vulnerability index by country_

| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `nd_gain_index` | Float32 | Overall ND-GAIN score 0-100 |
| `vulnerability` | Float32 |  |
| `readiness` | Float32 |  |
| `source_id` | UInt16 |  |

## Materialized-view targets (aggregates)

### `agg_co2_annual`
| Column | Type | Description |
|--------|------|-------------|
| `year` | UInt16 |  |
| `avg_ppm` | AggregateFunction(avg, Float32) |  |
| `max_ppm` | AggregateFunction(max, Float32) |  |

### `agg_disasters_by_type_decade`
| Column | Type | Description |
|--------|------|-------------|
| `decade` | UInt16 |  |
| `country_id` | UInt16 |  |
| `disaster_type_id` | UInt16 |  |
| `events` | UInt64 |  |
| `deaths` | UInt64 |  |
| `affected` | UInt64 |  |
| `damage_usd_k` | Float64 |  |

### `agg_emissions_by_decade`
| Column | Type | Description |
|--------|------|-------------|
| `decade` | UInt16 |  |
| `country_id` | UInt16 |  |
| `co2_mt_sum` | Float64 |  |
| `n_years` | UInt32 |  |

### `agg_renewables_annual`
| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `renewables_share` | AggregateFunction(avg, Float32) |  |
| `fossil_share` | AggregateFunction(avg, Float32) |  |
| `primary_energy` | AggregateFunction(avg, Float64) |  |

### `agg_temp_annual`
| Column | Type | Description |
|--------|------|-------------|
| `country_id` | UInt16 |  |
| `year` | UInt16 |  |
| `avg_anomaly` | AggregateFunction(avg, Float32) |  |
| `min_anomaly` | AggregateFunction(min, Float32) |  |
| `max_anomaly` | AggregateFunction(max, Float32) |  |
| `n_months` | AggregateFunction(count) |  |

## Lineage & audit

### `dq_audit_log`
_Automated data-quality audit results_

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | UUID |  |
| `run_ts` | DateTime |  |
| `check_name` | String |  |
| `check_category` | Enum8('COMPLETENESS' = 1, 'INTEGRITY' = 2, 'RANGE' = 3, 'UNIQUENESS' = 4, 'RECONCILIATION' = 5) |  |
| `target_table` | String |  |
| `target_column` | String |  |
| `metric_value` | Float64 |  |
| `threshold` | Float64 |  |
| `comparator` | LowCardinality(String) | <=, >=, =, <, > |
| `status` | Enum8('PASS' = 1, 'WARN' = 2, 'FAIL' = 3) |  |
| `details` | String |  |

### `meta_load_lineage`
_ETL load lineage / provenance log_

| Column | Type | Description |
|--------|------|-------------|
| `load_id` | UUID |  |
| `source_id` | UInt16 |  |
| `source_name` | String |  |
| `target_table` | String |  |
| `file_name` | String |  |
| `source_url` | String |  |
| `rows_loaded` | UInt64 |  |
| `load_started` | DateTime |  |
| `load_finished` | DateTime |  |
| `duration_s` | Float32 |  |
| `status` | Enum8('SUCCESS' = 1, 'PARTIAL' = 2, 'FAILED' = 3) |  |
| `checksum` | String |  |
| `access_date` | Date |  |
| `notes` | String |  |
