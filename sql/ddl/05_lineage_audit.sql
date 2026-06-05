-- ============================================================
-- 05_lineage_audit.sql  |  Data lineage + data-quality audit
-- Satisfies Goal 5 (data quality + lineage tracking layer).
-- ============================================================

-- ----------------------------------------------------------------
-- meta_load_lineage — one row per (source -> target table) load run.
-- Populated by the ETL loader (etl/load/clickhouse_loader.py).
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.meta_load_lineage
(
    load_id        UUID DEFAULT generateUUIDv4(),
    source_id      UInt16,
    source_name    String,
    target_table   String,
    file_name      String DEFAULT '',
    source_url     String DEFAULT '',
    rows_loaded    UInt64,
    load_started   DateTime,
    load_finished  DateTime,
    duration_s     Float32 MATERIALIZED dateDiff('second', load_started, load_finished),
    status         Enum8('SUCCESS' = 1, 'PARTIAL' = 2, 'FAILED' = 3) DEFAULT 'SUCCESS',
    checksum       String DEFAULT '',
    access_date    Date,
    notes          String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(load_started)
ORDER BY (target_table, load_started)
COMMENT 'ETL load lineage / provenance log';

-- ----------------------------------------------------------------
-- dq_audit_log — one row per data-quality check execution.
-- Populated by sql/dq/* checks driven from etl run / Makefile `dq` target.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS climate.dq_audit_log
(
    run_id         UUID,
    run_ts         DateTime DEFAULT now(),
    check_name     String,
    check_category Enum8('COMPLETENESS' = 1, 'INTEGRITY' = 2, 'RANGE' = 3, 'UNIQUENESS' = 4, 'RECONCILIATION' = 5),
    target_table   String,
    target_column  String DEFAULT '',
    metric_value   Float64,
    threshold      Float64,
    comparator     LowCardinality(String) COMMENT '<=, >=, =, <, >',
    status         Enum8('PASS' = 1, 'WARN' = 2, 'FAIL' = 3),
    details        String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(run_ts)
ORDER BY (run_ts, check_category, check_name)
COMMENT 'Automated data-quality audit results';
