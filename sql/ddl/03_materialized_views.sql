-- ============================================================
-- 03_materialized_views.sql  |  Materialized views (>=5, incremental + refreshable).
--
-- Incremental MVs are insert-triggered, so this file runs BEFORE the ETL load
-- (the init sequence does that). If data was loaded first, backfill with the
-- INSERT...SELECT shown under each MV.
--
-- 5 incremental MVs (AggregatingMergeTree / SummingMergeTree)
-- 1 refreshable MV  (scheduled wide country-year overview with JOINs)
-- ============================================================

-- ------------------------------------------------------------
-- MV 1 (incremental, SummingMergeTree): emissions rolled to decade
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.agg_emissions_by_decade
(
    decade     UInt16,
    country_id UInt16,
    co2_mt_sum Float64,
    n_years    UInt32
)
ENGINE = SummingMergeTree
ORDER BY (decade, country_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS climate.mv_emissions_by_decade
TO climate.agg_emissions_by_decade AS
SELECT
    toUInt16(intDiv(year, 10) * 10) AS decade,
    country_id,
    sum(co2_mt)                     AS co2_mt_sum,
    count()                         AS n_years
FROM climate.fact_emissions_co2
WHERE source_id = 1                 -- OWID canonical (avoid double-count with GCB)
GROUP BY decade, country_id;

-- ------------------------------------------------------------
-- MV 2 (incremental, AggregatingMergeTree): annual temperature anomaly
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.agg_temp_annual
(
    country_id  UInt16,
    year        UInt16,
    avg_anomaly AggregateFunction(avg, Float32),
    min_anomaly AggregateFunction(min, Float32),
    max_anomaly AggregateFunction(max, Float32),
    n_months    AggregateFunction(count)
)
ENGINE = AggregatingMergeTree
ORDER BY (country_id, year);

CREATE MATERIALIZED VIEW IF NOT EXISTS climate.mv_temp_annual
TO climate.agg_temp_annual AS
SELECT
    country_id,
    toYear(date)              AS year,
    avgState(temp_anomaly_c)  AS avg_anomaly,
    minState(temp_anomaly_c)  AS min_anomaly,
    maxState(temp_anomaly_c)  AS max_anomaly,
    countState()              AS n_months
FROM climate.fact_temperature
GROUP BY country_id, year;
-- query with: avgMerge(avg_anomaly), minMerge(min_anomaly), maxMerge(max_anomaly), countMerge(n_months)

-- ------------------------------------------------------------
-- MV 3 (incremental, AggregatingMergeTree): annual atmospheric CO2
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.agg_co2_annual
(
    year    UInt16,
    avg_ppm AggregateFunction(avg, Float32),
    max_ppm AggregateFunction(max, Float32)
)
ENGINE = AggregatingMergeTree
ORDER BY year;

CREATE MATERIALIZED VIEW IF NOT EXISTS climate.mv_co2_annual
TO climate.agg_co2_annual AS
SELECT
    toYear(date)        AS year,
    avgState(co2_ppm)   AS avg_ppm,
    maxState(co2_ppm)   AS max_ppm
FROM climate.fact_co2_atmospheric
GROUP BY year;

-- ------------------------------------------------------------
-- MV 4 (incremental, SummingMergeTree): disasters by type & decade
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.agg_disasters_by_type_decade
(
    decade           UInt16,
    country_id       UInt16,
    disaster_type_id UInt16,
    events           UInt64,
    deaths           UInt64,
    affected         UInt64,
    damage_usd_k     Float64
)
ENGINE = SummingMergeTree
ORDER BY (decade, country_id, disaster_type_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS climate.mv_disasters_by_type_decade
TO climate.agg_disasters_by_type_decade AS
SELECT
    toUInt16(intDiv(year, 10) * 10) AS decade,
    country_id,
    disaster_type_id,
    sum(events)             AS events,
    sum(total_deaths)       AS deaths,
    sum(total_affected)     AS affected,
    sum(total_damage_usd_k) AS damage_usd_k
FROM climate.fact_disasters
GROUP BY decade, country_id, disaster_type_id;

-- ------------------------------------------------------------
-- MV 5 (incremental, AggregatingMergeTree): annual energy mix
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.agg_renewables_annual
(
    country_id       UInt16,
    year             UInt16,
    renewables_share AggregateFunction(avg, Float32),
    fossil_share     AggregateFunction(avg, Float32),
    primary_energy   AggregateFunction(avg, Float64)
)
ENGINE = AggregatingMergeTree
ORDER BY (country_id, year);

CREATE MATERIALIZED VIEW IF NOT EXISTS climate.mv_renewables_annual
TO climate.agg_renewables_annual AS
SELECT
    country_id,
    year,
    avgState(renewables_share_pct) AS renewables_share,
    avgState(fossil_share_pct)     AS fossil_share,
    avgState(primary_energy_twh)   AS primary_energy
FROM climate.fact_energy
GROUP BY country_id, year;

-- ------------------------------------------------------------
-- MV 6 (REFRESHABLE): wide country-year analytical overview.
-- Joins 4 facts into one denormalized table; rebuilt on a schedule.
-- Indicator IDs (dim_indicator): 1=GDP (current US$), 2=Population.
-- Requires: SET allow_experimental_refreshable_materialized_view = 1;
-- ------------------------------------------------------------
SET allow_experimental_refreshable_materialized_view = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS climate.mv_country_year_overview
REFRESH EVERY 1 DAY
ENGINE = MergeTree
ORDER BY (country_id, year)
AS
SELECT
    e.country_id                         AS country_id,
    e.year                               AS year,
    e.co2_mt                             AS co2_mt,
    e.co2_per_capita_t                   AS co2_per_capita_t,
    en.primary_energy_twh                AS primary_energy_twh,
    en.renewables_share_pct              AS renewables_share_pct,
    gdp.value                            AS gdp_usd,
    pop.value                            AS population,
    if(pop.value > 0, gdp.value / pop.value, 0) AS gdp_per_capita_usd,
    v.nd_gain_index                      AS nd_gain_index
FROM (SELECT * FROM climate.fact_emissions_co2 WHERE source_id = 1) AS e
LEFT JOIN climate.fact_energy AS en
       ON e.country_id = en.country_id AND e.year = en.year
LEFT JOIN (SELECT country_id, year, value FROM climate.fact_socioeconomic WHERE indicator_id = 1) AS gdp
       ON e.country_id = gdp.country_id AND e.year = gdp.year
LEFT JOIN (SELECT country_id, year, value FROM climate.fact_socioeconomic WHERE indicator_id = 2) AS pop
       ON e.country_id = pop.country_id AND e.year = pop.year
LEFT JOIN climate.fact_vulnerability AS v
       ON e.country_id = v.country_id AND e.year = v.year;
