"""Automated data-quality checks (Goal 5).

Each check runs one scalar SQL and compares it against a threshold; results are
written to climate.dq_audit_log with PASS / WARN / FAIL. The check SET is
engine-agnostic SQL so it runs against the production ClickHouse client OR the
embedded chdb test harness (see scripts/validate_local.py).

CLI:  python -m etl.dq          # run against ClickHouse, log to dq_audit_log
"""
from __future__ import annotations
import datetime as dt
import uuid
import operator

_OPS = {"<=": operator.le, ">=": operator.ge, "=": operator.eq,
        "<": operator.lt, ">": operator.gt, "!=": operator.ne}

# name, category, table, column, comparator, threshold, sql(-> single scalar)
CHECKS = [
    ("orphan_country_emissions", "INTEGRITY", "fact_emissions_co2", "country_id", "=", 0,
     "SELECT count() FROM climate.fact_emissions_co2 WHERE country_id NOT IN "
     "(SELECT country_id FROM climate.dim_country)"),
    ("orphan_indicator_socio", "INTEGRITY", "fact_socioeconomic", "indicator_id", "=", 0,
     "SELECT count() FROM climate.fact_socioeconomic WHERE indicator_id NOT IN "
     "(SELECT indicator_id FROM climate.dim_indicator)"),
    ("orphan_disaster_type", "INTEGRITY", "fact_disasters", "disaster_type_id", "=", 0,
     "SELECT count() FROM climate.fact_disasters WHERE disaster_type_id NOT IN "
     "(SELECT disaster_type_id FROM climate.dim_disaster_type)"),
    ("null_rate_co2", "COMPLETENESS", "fact_emissions_co2", "co2_mt", "<=", 0.02,
     "SELECT countIf(isNaN(co2_mt) OR co2_mt IS NULL) / greatest(count(), 1) "
     "FROM climate.fact_emissions_co2"),
    ("co2_per_capita_range", "RANGE", "fact_emissions_co2", "co2_per_capita_t", "=", 0,
     "SELECT countIf(co2_per_capita_t < 0 OR co2_per_capita_t > 1000) "
     "FROM climate.fact_emissions_co2"),
    ("renewables_share_range", "RANGE", "fact_energy", "renewables_share_pct", "=", 0,
     "SELECT countIf(renewables_share_pct < 0 OR renewables_share_pct > 100) "
     "FROM climate.fact_energy"),
    ("temp_anomaly_range", "RANGE", "fact_temperature", "temp_anomaly_c", "=", 0,
     "SELECT countIf(temp_anomaly_c < -15 OR temp_anomaly_c > 15) "
     "FROM climate.fact_temperature"),
    ("dup_emissions_key", "UNIQUENESS", "fact_emissions_co2", "country_id,year,source_id", "=", 0,
     "SELECT count() - countDistinct((country_id, year, source_id)) "
     "FROM climate.fact_emissions_co2 FINAL"),
    ("year_coverage_emissions", "COMPLETENESS", "fact_emissions_co2", "year", ">=", 40,
     "SELECT countDistinct(year) FROM climate.fact_emissions_co2"),
    ("country_coverage_socio", "COMPLETENESS", "fact_socioeconomic", "country_id", ">=", 100,
     "SELECT countDistinct(country_id) FROM climate.fact_socioeconomic"),
    # Cross-source reconciliation: OWID (1) vs GCB (8) CO2, mean abs % diff.
    ("recon_owid_vs_gcb", "RECONCILIATION", "fact_emissions_co2", "co2_mt", "<=", 15.0,
     "SELECT round(avg(abs(a.co2_mt - b.co2_mt) / nullIf(a.co2_mt, 0)) * 100, 2) "
     "FROM (SELECT country_id, year, co2_mt FROM climate.fact_emissions_co2 WHERE source_id = 1) a "
     "INNER JOIN (SELECT country_id, year, co2_mt FROM climate.fact_emissions_co2 WHERE source_id = 8) b "
     "ON a.country_id = b.country_id AND a.year = b.year"),
]


def evaluate(metric, comparator: str, threshold: float) -> str:
    if metric is None:
        return "WARN"
    try:
        return "PASS" if _OPS[comparator](float(metric), float(threshold)) else "FAIL"
    except (TypeError, ValueError):
        return "WARN"


def run(query_scalar, log_row=None, verbose: bool = True):
    """query_scalar(sql) -> first cell (or None). log_row(tuple) optional."""
    run_id = str(uuid.uuid4())
    now = dt.datetime.now().replace(microsecond=0)
    results, npass = [], 0
    if verbose:
        print(f"{'check':28} {'category':14} {'metric':>12} {'thr':>8}  status")
        print("-" * 78)
    for name, cat, table, col, comp, thr, sql in CHECKS:
        try:
            metric = query_scalar(sql)
        except Exception as e:
            metric, status, detail = None, "WARN", str(e).splitlines()[0][:120]
        else:
            status = evaluate(metric, comp, thr)
            detail = f"{comp} {thr}"
        if status == "PASS":
            npass += 1
        row = (run_id, now, name, cat, table, col,
               float(metric) if metric is not None else 0.0, float(thr), comp, status, detail)
        results.append(row)
        if log_row:
            log_row(row)
        if verbose:
            mv = "—" if metric is None else f"{float(metric):.4g}"
            print(f"{name:28} {cat:14} {mv:>12} {thr:>8}  {status}")
    rate = 100.0 * npass / len(CHECKS)
    if verbose:
        print("-" * 78)
        print(f"PASS rate: {npass}/{len(CHECKS)} = {rate:.1f}%")
    return results, rate


def run_production(client):
    from .config import DATABASE

    def scalar(sql):
        r = client.query(sql).result_rows
        return r[0][0] if r and r[0] else None

    def log(row):
        client.insert(f"{DATABASE}.dq_audit_log", [list(row)],
                      column_names=["run_id", "run_ts", "check_name", "check_category",
                                    "target_table", "target_column", "metric_value",
                                    "threshold", "comparator", "status", "details"])
    return run(scalar, log)


if __name__ == "__main__":
    from .db import get_client
    run_production(get_client(database="climate"))
