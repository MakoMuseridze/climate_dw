-- ============================================================
-- 02_facts.sql  |  Fact tables (star-schema)
-- 12 fact tables across six themes: Emissions(3), Energy(1),
-- Atmosphere(4), Agriculture(1), Disasters(1), Socioeconomic(2).
-- source_id is in the sort key for multi-source facts (OWID+GCB CO2,
-- GISTEMP+HadCRUT5+ERA5 temperature, GPCC+CHIRPS precip) so they coexist.
-- ReplacingMergeTree(_inserted_at) makes re-runs idempotent.
-- ============================================================

-- THEME 1: GREENHOUSE-GAS EMISSIONS ----------------------------------
CREATE TABLE IF NOT EXISTS climate.fact_emissions_co2
(
    country_id        UInt16,
    year              UInt16,
    co2_mt            Float64  COMMENT 'Total CO2, million tonnes',
    co2_per_capita_t  Float64,
    co2_per_gdp_kg    Float64  COMMENT 'kg CO2 per USD GDP',
    coal_co2_mt       Float64 DEFAULT 0,
    oil_co2_mt        Float64 DEFAULT 0,
    gas_co2_mt        Float64 DEFAULT 0,
    cement_co2_mt     Float64 DEFAULT 0,
    cumulative_co2_mt Float64 DEFAULT 0,
    share_global_co2  Float32 DEFAULT 0,
    source_id         UInt16,
    _inserted_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(year, 10) * 10)
ORDER BY (country_id, year, source_id)
COMMENT 'Annual CO2 emissions by country (OWID + GCB coexist via source_id)';

CREATE TABLE IF NOT EXISTS climate.fact_ghg_emissions
(
    country_id         UInt16,
    year               UInt16,
    ghg_total_mt_co2e  Float64,
    ch4_mt_co2e        Float64 DEFAULT 0,
    n2o_mt_co2e        Float64 DEFAULT 0,
    ghg_per_capita_t   Float64 DEFAULT 0,
    source_id          UInt16,
    _inserted_at       DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(year, 10) * 10)
ORDER BY (country_id, year, source_id)
COMMENT 'Annual total greenhouse-gas emissions by country';

CREATE TABLE IF NOT EXISTS climate.fact_emissions_by_sector
(
    country_id        UInt16,
    year              UInt16,
    sector_id         UInt16,
    gas               LowCardinality(String) COMMENT 'CO2 / CH4 / N2O',
    emissions_mt_co2e Float64,
    source_id         UInt16,
    _inserted_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(year, 10) * 10)
ORDER BY (country_id, year, sector_id, gas, source_id)
COMMENT 'Annual emissions by sector and gas (EDGAR + Climate TRACE)';

-- THEME 2: ENERGY ----------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.fact_energy
(
    country_id            UInt16,
    year                  UInt16,
    primary_energy_twh    Float64,
    fossil_share_pct      Float32 DEFAULT 0,
    renewables_share_pct  Float32 DEFAULT 0,
    nuclear_share_pct     Float32 DEFAULT 0,
    low_carbon_share_pct  Float32 DEFAULT 0,
    electricity_demand_twh Float64 DEFAULT 0,
    energy_per_capita_kwh Float64 DEFAULT 0,
    source_id             UInt16,
    _inserted_at          DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(year, 10) * 10)
ORDER BY (country_id, year)
COMMENT 'Annual energy consumption and generation mix by country';

-- THEME 3: ATMOSPHERIC OBSERVATIONS ----------------------------------
CREATE TABLE IF NOT EXISTS climate.fact_temperature
(
    country_id     UInt16,
    date           Date32 COMMENT 'Month start (YYYY-MM-01)',
    temp_anomaly_c Float32 COMMENT 'Anomaly vs 1951-1980 baseline',
    temp_abs_c     Nullable(Float32),
    source_id      UInt16,
    _inserted_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(toYear(date), 10) * 10)
ORDER BY (country_id, date, source_id)
COMMENT 'Monthly temperature anomaly (country_id 0 = global, multi-source)';

CREATE TABLE IF NOT EXISTS climate.fact_co2_atmospheric
(
    date           Date32 COMMENT 'Month start',
    station        LowCardinality(String) DEFAULT 'Mauna Loa',
    co2_ppm        Float32,
    co2_trend_ppm  Float32 DEFAULT 0,
    source_id      UInt16,
    _inserted_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
ORDER BY (station, date)
COMMENT 'Monthly atmospheric CO2 (ppm)';

CREATE TABLE IF NOT EXISTS climate.fact_precipitation
(
    country_id   UInt16,
    date         Date32 COMMENT 'Month start',
    precip_mm    Float32,
    source_id    UInt16,
    _inserted_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(toYear(date), 10) * 10)
ORDER BY (country_id, date, source_id)
COMMENT 'Monthly precipitation by country (mm, GPCC + CHIRPS)';

CREATE TABLE IF NOT EXISTS climate.fact_sea_level
(
    date                 Date32,
    gmsl_mm              Float32 COMMENT 'Global mean sea level vs baseline',
    gmsl_uncertainty_mm  Float32 DEFAULT 0,
    source_id            UInt16,
    _inserted_at         DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
ORDER BY date
COMMENT 'Global mean sea level (mm)';

-- THEME 4: NATURAL DISASTERS -----------------------------------------
CREATE TABLE IF NOT EXISTS climate.fact_disasters
(
    country_id        UInt16,
    year              UInt16,
    disaster_type_id  UInt16,
    events            UInt32,
    total_deaths      UInt64 DEFAULT 0,
    total_affected    UInt64 DEFAULT 0,
    total_damage_usd_k Float64 DEFAULT 0 COMMENT 'Total damage, thousands USD',
    source_id         UInt16,
    _inserted_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(year, 10) * 10)
ORDER BY (country_id, year, disaster_type_id)
COMMENT 'Annual natural-disaster impacts by country and type';

-- THEME 5: AGRICULTURE & LAND USE ------------------------------------
CREATE TABLE IF NOT EXISTS climate.fact_agriculture
(
    country_id   UInt16,
    year         UInt16,
    item         LowCardinality(String) COMMENT 'e.g. Cereals, Forest land, Rice',
    element      LowCardinality(String) COMMENT 'e.g. Area harvested, Production',
    value        Float64,
    unit         LowCardinality(String),
    source_id    UInt16,
    _inserted_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(year, 10) * 10)
ORDER BY (country_id, year, item, element)
COMMENT 'Annual agriculture & land-use metrics by country';

-- THEME 6: SOCIOECONOMIC ---------------------------------------------
CREATE TABLE IF NOT EXISTS climate.fact_socioeconomic
(
    country_id   UInt16,
    indicator_id UInt32,
    year         UInt16,
    value        Float64,
    source_id    UInt16,
    _inserted_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(year, 10) * 10)
ORDER BY (indicator_id, country_id, year)
COMMENT 'Annual socioeconomic indicators (GDP, population, urbanization, etc.)';

CREATE TABLE IF NOT EXISTS climate.fact_vulnerability
(
    country_id     UInt16,
    year           UInt16,
    nd_gain_index  Float32 COMMENT 'Overall ND-GAIN score 0-100',
    vulnerability  Float32,
    readiness      Float32,
    source_id      UInt16,
    _inserted_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_inserted_at)
PARTITION BY toUInt16(intDiv(year, 10) * 10)
ORDER BY (country_id, year)
COMMENT 'Annual ND-GAIN climate vulnerability index by country';
