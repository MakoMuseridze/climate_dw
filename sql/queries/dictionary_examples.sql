-- ============================================================
-- dictionary_examples.sql  |  dictGet()-accelerated lookups
-- Demonstrates external dictionaries (04_dictionaries.sql) replacing JOINs
-- with O(1) in-memory lookups. Validated on the Docker ClickHouse deployment
-- (dictionaries require a running server).
-- ============================================================

-- D1 — CO2 per capita by income group, using dictGet instead of a JOIN to dim_country
SELECT
    dictGet('climate.dict_country', 'income_group', toUInt64(country_id)) AS income_group,
    year,
    round(avg(co2_per_capita_t), 2) AS avg_co2_per_capita_t
FROM climate.fact_emissions_co2
WHERE source_id = 1 AND year = 2020
GROUP BY income_group, year
ORDER BY avg_co2_per_capita_t DESC;

-- D2 — Disaster deaths by region + disaster type, both via dictGet
SELECT
    dictGet('climate.dict_country', 'region', toUInt64(country_id))            AS region,
    dictGet('climate.dict_disaster_type', 'disaster_type', toUInt64(disaster_type_id)) AS disaster_type,
    sum(total_deaths) AS deaths
FROM climate.fact_disasters
GROUP BY region, disaster_type
ORDER BY deaths DESC
LIMIT 25;

-- D3 — Socioeconomic value labelled with indicator metadata via dictGet
SELECT
    dictGet('climate.dict_country', 'country_name', toUInt64(country_id))   AS country,
    dictGet('climate.dict_indicator', 'indicator_name', toUInt64(indicator_id)) AS indicator,
    year,
    value
FROM climate.fact_socioeconomic
WHERE indicator_id = 3 AND year = 2020
ORDER BY value DESC
LIMIT 10;
