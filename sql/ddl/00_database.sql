-- ============================================================
-- 00_database.sql  |  Global Climate Data Warehouse
-- Creates the warehouse database. Run FIRST.
-- Target: ClickHouse 24.x
-- ============================================================

CREATE DATABASE IF NOT EXISTS climate
    COMMENT 'Global Climate Data Warehouse — environmental + socioeconomic integration';

-- All subsequent objects live in the `climate` database and are
-- fully qualified (climate.<object>) so the scripts are order-independent
-- beyond this file.
