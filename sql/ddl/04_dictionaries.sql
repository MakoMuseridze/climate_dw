-- ============================================================
-- 04_dictionaries.sql  |  External dictionaries for fast dimension lookups
--
-- Dictionaries give O(1) in-memory lookups (dictGet) instead of JOINs,
-- which keeps wide analytical queries sub-second.
--
-- NOTE: ClickHouse-sourced dictionaries require a running ClickHouse server
-- (they read over the native protocol). They are created/validated on the
-- Docker deployment, not in the embedded chdb test harness.
--
-- Usage example:
--   SELECT dictGet('climate.dict_country', 'income_group', toUInt64(country_id))
-- ============================================================

-- dict_country — country attributes keyed by surrogate id (current rows only).
CREATE DICTIONARY IF NOT EXISTS climate.dict_country
(
    country_id   UInt64,
    iso3         String,
    country_name String,
    region       String,
    subregion    String,
    income_group String,
    continent    String
)
PRIMARY KEY country_id
SOURCE(CLICKHOUSE(
    QUERY 'SELECT country_id, iso3, country_name, region, subregion, income_group, continent FROM climate.dim_country WHERE is_current = 1'
))
LAYOUT(HASHED())
LIFETIME(MIN 600 MAX 1200);

-- dict_indicator — indicator metadata keyed by indicator_id.
CREATE DICTIONARY IF NOT EXISTS climate.dict_indicator
(
    indicator_id   UInt64,
    indicator_code String,
    indicator_name String,
    unit           String,
    theme          String
)
PRIMARY KEY indicator_id
SOURCE(CLICKHOUSE(
    QUERY 'SELECT indicator_id, indicator_code, indicator_name, unit, theme FROM climate.dim_indicator'
))
LAYOUT(HASHED())
LIFETIME(MIN 600 MAX 1200);

-- dict_disaster_type — disaster classification keyed by id.
CREATE DICTIONARY IF NOT EXISTS climate.dict_disaster_type
(
    disaster_type_id  UInt64,
    disaster_group    String,
    disaster_subgroup String,
    disaster_type     String
)
PRIMARY KEY disaster_type_id
SOURCE(CLICKHOUSE(
    QUERY 'SELECT disaster_type_id, disaster_group, disaster_subgroup, disaster_type FROM climate.dim_disaster_type'
))
LAYOUT(HASHED())
LIFETIME(MIN 600 MAX 1200);
