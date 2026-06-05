-- ============================================================
-- 01_dimensions.sql  |  Dimension tables (star-schema)
-- 6 conformed dimensions shared across all fact tables.
-- Engine: ReplacingMergeTree (idempotent re-loads dedup to latest _version).
-- ============================================================

-- ----------------------------------------------------------------
-- dim_country — the central conformed dimension.
-- Includes SCD Type 2 columns (valid_from / valid_to / is_current)
-- to track income-group reclassifications over time.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.dim_country
(
    country_id    UInt16            COMMENT 'Surrogate key',
    iso3          FixedString(3)    COMMENT 'ISO 3166-1 alpha-3 (e.g. USA, GEO)',
    iso2          FixedString(2)    COMMENT 'ISO 3166-1 alpha-2',
    country_name  String,
    region        LowCardinality(String) COMMENT 'World Bank region',
    subregion     LowCardinality(String),
    continent     LowCardinality(String),
    income_group  LowCardinality(String) COMMENT 'WB: Low / Lower-middle / Upper-middle / High',
    un_member     UInt8 DEFAULT 1,
    area_km2      Float64 DEFAULT 0,
    -- SCD Type 2
    valid_from    Date32 DEFAULT toDate32('1900-01-01'),
    valid_to      Date32 DEFAULT toDate32('2200-01-01'),
    is_current    UInt8 DEFAULT 1,
    _version      UInt64 DEFAULT toUnixTimestamp(now())
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY (country_id, valid_from)
COMMENT 'Conformed country dimension (SCD2-capable)';

-- ----------------------------------------------------------------
-- dim_date — daily calendar dimension (1850-01-01 .. 2024-12-31).
-- Monthly/daily facts join on `date`; annual facts use the year column directly.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.dim_date
(
    date           Date32,
    year           UInt16,
    month          UInt8,
    day            UInt8,
    quarter        UInt8,
    decade         UInt16,
    day_of_year    UInt16,
    month_name     LowCardinality(String),
    is_year_start  UInt8,
    is_month_start UInt8
)
ENGINE = MergeTree
ORDER BY date
COMMENT 'Calendar dimension';

-- ----------------------------------------------------------------
-- dim_indicator — socioeconomic indicators (World Bank WDI) and
-- any other code/unit-driven measures stored tall in fact_socioeconomic.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.dim_indicator
(
    indicator_id   UInt32,
    indicator_code String            COMMENT 'e.g. NY.GDP.MKTP.CD',
    indicator_name String,
    unit           LowCardinality(String),
    theme          LowCardinality(String),
    source         LowCardinality(String) DEFAULT 'World Bank WDI',
    _version       UInt64 DEFAULT toUnixTimestamp(now())
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY indicator_id
COMMENT 'Indicator dimension for tall socioeconomic facts';

-- ----------------------------------------------------------------
-- dim_disaster_type — EM-DAT disaster classification hierarchy.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.dim_disaster_type
(
    disaster_type_id  UInt16,
    disaster_group    LowCardinality(String) COMMENT 'Natural / Technological',
    disaster_subgroup LowCardinality(String) COMMENT 'Geophysical / Meteorological / Hydrological / Climatological / Biological',
    disaster_type     LowCardinality(String) COMMENT 'Flood / Storm / Drought / Earthquake / Wildfire ...',
    disaster_subtype  String DEFAULT '',
    _version          UInt64 DEFAULT toUnixTimestamp(now())
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY disaster_type_id
COMMENT 'EM-DAT disaster type hierarchy';

-- ----------------------------------------------------------------
-- dim_sector — emissions sectors (EDGAR / Climate TRACE).
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.dim_sector
(
    sector_id   UInt16,
    sector_name LowCardinality(String) COMMENT 'Energy / Industry / Transport / Agriculture / Waste / Buildings',
    ipcc_code   String DEFAULT '',
    _version    UInt64 DEFAULT toUnixTimestamp(now())
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY sector_id
COMMENT 'Emissions sector dimension';

-- ----------------------------------------------------------------
-- dim_source — data-source registry. Also the anchor for lineage:
-- every fact row carries source_id; full provenance lives here +
-- in meta_load_lineage (see 05_lineage_audit.sql).
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.dim_source
(
    source_id   UInt16,
    source_name String,
    domain      LowCardinality(String) COMMENT 'Emissions / Energy / Temperature / Disasters / ...',
    format      LowCardinality(String) COMMENT 'CSV / Excel / NetCDF / API / TXT',
    url         String,
    license     String DEFAULT '',
    coverage    String DEFAULT '',
    _version    UInt64 DEFAULT toUnixTimestamp(now())
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY source_id
COMMENT 'Source registry (provenance)';
