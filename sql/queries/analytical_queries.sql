-- ============================================================
-- analytical_queries.sql  |  Cross-domain analytical query library
-- 12 queries spanning all six themes. Target: < 2 s on the full warehouse.
-- Written with explicit JOINs to dimensions (portable); dictionary-accelerated
-- variants are in dictionary_examples.sql.
-- Convention: emissions queries filter source_id = 1 (OWID) as the canonical CO2.
-- ============================================================

-- Q1 — Emissions vs GDP correlation (cross-country, latest full year)
-- Theme: Emissions x Socioeconomic
SELECT
    e.year,
    round(corr(e.co2_mt, g.value), 3)              AS co2_gdp_correlation,
    round(corr(e.co2_per_capita_t, gpc.value), 3)  AS co2pc_gdppc_correlation,
    count()                                         AS n_countries
FROM climate.fact_emissions_co2 AS e
INNER JOIN (SELECT country_id, year, value FROM climate.fact_socioeconomic WHERE indicator_id = 1) AS g
        ON e.country_id = g.country_id AND e.year = g.year
INNER JOIN (SELECT country_id, year, value FROM climate.fact_socioeconomic WHERE indicator_id = 3) AS gpc
        ON e.country_id = gpc.country_id AND e.year = gpc.year
WHERE e.source_id = 1 AND e.year = 2020
GROUP BY e.year;

-- Q2 — Top 15 cumulative CO2 emitters (historical responsibility)
-- Theme: Emissions
SELECT
    c.country_name,
    c.income_group,
    round(max(e.cumulative_co2_mt) / 1000, 1)       AS cumulative_gt_co2
FROM climate.fact_emissions_co2 AS e
INNER JOIN climate.dim_country AS c ON e.country_id = c.country_id
WHERE e.source_id = 1
GROUP BY c.country_name, c.income_group
ORDER BY cumulative_gt_co2 DESC
LIMIT 15;

-- Q3 — Disaster frequency & deaths by income group and decade
-- Theme: Disasters x Socioeconomic  (uses MV agg_disasters_by_type_decade)
SELECT
    c.income_group,
    d.decade,
    sum(d.events)        AS events,
    sum(d.deaths)        AS deaths,
    round(sum(d.damage_usd_k) / 1e6, 2) AS damage_bn_usd
FROM climate.agg_disasters_by_type_decade AS d
INNER JOIN climate.dim_country AS c ON d.country_id = c.country_id
GROUP BY c.income_group, d.decade
ORDER BY d.decade, c.income_group;

-- Q4 — Renewable-energy transition by region over time
-- Theme: Energy
SELECT
    c.region,
    en.year,
    round(avg(en.renewables_share_pct), 1) AS avg_renewables_pct,
    round(avg(en.fossil_share_pct), 1)     AS avg_fossil_pct
FROM climate.fact_energy AS en
INNER JOIN climate.dim_country AS c ON en.country_id = c.country_id
WHERE en.year >= 1990
GROUP BY c.region, en.year
ORDER BY c.region, en.year;

-- Q5 — Global temperature anomaly vs atmospheric CO2 (annual)
-- Theme: Atmospheric  (uses MVs agg_temp_annual + agg_co2_annual)
SELECT
    t.year,
    round(avgMerge(t.avg_anomaly), 3) AS global_temp_anomaly_c,
    round(any(co2.ppm), 2)            AS atmospheric_co2_ppm
FROM climate.agg_temp_annual AS t
LEFT JOIN (
    SELECT year, avgMerge(avg_ppm) AS ppm FROM climate.agg_co2_annual GROUP BY year
) AS co2 ON t.year = co2.year
WHERE t.country_id = 0
GROUP BY t.year
ORDER BY t.year;

-- Q6 — CO2 per capita by income group over time
-- Theme: Emissions x Socioeconomic
SELECT
    c.income_group,
    e.year,
    round(avg(e.co2_per_capita_t), 2) AS avg_co2_per_capita_t
FROM climate.fact_emissions_co2 AS e
INNER JOIN climate.dim_country AS c ON e.country_id = c.country_id
WHERE e.source_id = 1 AND e.year >= 1970 AND c.income_group != 'Aggregate'
GROUP BY c.income_group, e.year
ORDER BY e.year, c.income_group;

-- Q7 — Decoupling: GDP growth vs emissions change, 2000 -> 2020
-- Theme: Emissions x Socioeconomic
WITH em AS (
    SELECT country_id, year, co2_mt FROM climate.fact_emissions_co2 WHERE source_id = 1 AND year IN (2000, 2020)
),
gd AS (
    SELECT country_id, year, value AS gdp FROM climate.fact_socioeconomic WHERE indicator_id = 1 AND year IN (2000, 2020)
)
SELECT
    c.country_name,
    round((maxIf(em.co2_mt, em.year = 2020) - maxIf(em.co2_mt, em.year = 2000))
          / nullIf(maxIf(em.co2_mt, em.year = 2000), 0) * 100, 1) AS co2_change_pct,
    round((maxIf(gd.gdp, gd.year = 2020) - maxIf(gd.gdp, gd.year = 2000))
          / nullIf(maxIf(gd.gdp, gd.year = 2000), 0) * 100, 1)    AS gdp_change_pct
FROM em
INNER JOIN gd ON em.country_id = gd.country_id AND em.year = gd.year
INNER JOIN climate.dim_country AS c ON em.country_id = c.country_id
GROUP BY c.country_name
HAVING co2_change_pct < 0 AND gdp_change_pct > 0   -- absolute decoupling
ORDER BY gdp_change_pct DESC
LIMIT 20;

-- Q8 — Disaster damage vs climate vulnerability (ND-GAIN)
-- Theme: Disasters x Vulnerability
SELECT
    c.income_group,
    round(avg(v.nd_gain_index), 1)                 AS avg_nd_gain,
    round(avg(v.vulnerability), 3)                 AS avg_vulnerability,
    round(sum(d.total_damage_usd_k) / 1e6, 1)      AS total_damage_bn_usd,
    sum(d.total_deaths)                            AS total_deaths
FROM climate.fact_disasters AS d
INNER JOIN climate.dim_country AS c ON d.country_id = c.country_id
LEFT JOIN (SELECT country_id, avg(nd_gain_index) nd_gain_index, avg(vulnerability) vulnerability
           FROM climate.fact_vulnerability GROUP BY country_id) AS v
       ON d.country_id = v.country_id
WHERE d.year >= 2000
GROUP BY c.income_group
ORDER BY total_damage_bn_usd DESC;

-- Q9 — Renewable-transition leaders (largest gain in renewables share 2000->2020)
-- Theme: Energy
SELECT
    c.country_name,
    round(maxIf(en.renewables_share_pct, en.year = 2000), 1) AS renew_2000,
    round(maxIf(en.renewables_share_pct, en.year = 2020), 1) AS renew_2020,
    round(maxIf(en.renewables_share_pct, en.year = 2020)
          - maxIf(en.renewables_share_pct, en.year = 2000), 1) AS gain_pp
FROM climate.fact_energy AS en
INNER JOIN climate.dim_country AS c ON en.country_id = c.country_id
WHERE en.year IN (2000, 2020)
GROUP BY c.country_name
ORDER BY gain_pp DESC
LIMIT 20;

-- Q10 — Carbon intensity of the economy (kg CO2 per $) by region, decade
-- Theme: Emissions x Socioeconomic
SELECT
    c.region,
    toUInt16(intDiv(e.year, 10) * 10) AS decade,
    round(avg(e.co2_per_gdp_kg), 4)   AS avg_kg_co2_per_usd
FROM climate.fact_emissions_co2 AS e
INNER JOIN climate.dim_country AS c ON e.country_id = c.country_id
WHERE e.source_id = 1 AND e.co2_per_gdp_kg > 0 AND c.income_group != 'Aggregate'
GROUP BY c.region, decade
ORDER BY c.region, decade;

-- Q11 — Sea-level rise rate per decade
-- Theme: Atmospheric / Ocean
SELECT
    toUInt16(intDiv(toYear(date), 10) * 10) AS decade,
    round(avg(gmsl_mm), 1)                  AS avg_gmsl_mm,
    round(max(gmsl_mm) - min(gmsl_mm), 1)   AS range_mm
FROM climate.fact_sea_level
GROUP BY decade
ORDER BY decade;

-- Q12 — Agriculture footprint: production vs agricultural emissions
-- Theme: Agriculture x Emissions
SELECT
    c.region,
    a.year,
    round(sum(a.value) / 1e6, 1)            AS production_mt,
    round(sum(s.emissions_mt_co2e), 1)      AS agri_emissions_mt_co2e
FROM (SELECT country_id, year, value FROM climate.fact_agriculture
      WHERE element = 'Production') AS a
INNER JOIN climate.dim_country AS c ON a.country_id = c.country_id
LEFT JOIN (SELECT country_id, year, sum(emissions_mt_co2e) emissions_mt_co2e
           FROM climate.fact_emissions_by_sector WHERE sector_id = 4 GROUP BY country_id, year) AS s
       ON a.country_id = s.country_id AND a.year = s.year
WHERE a.year >= 2000
GROUP BY c.region, a.year
ORDER BY c.region, a.year;
