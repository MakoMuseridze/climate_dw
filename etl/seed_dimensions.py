"""Seed all dimension / reference tables. Run AFTER the DDL, BEFORE fact ETL."""
from __future__ import annotations
import pandas as pd

from .config import DATABASE
from .dimensions import (build_source_dim, build_country_dim, build_indicator_dim,
                         build_disaster_dim, build_sector_dim, build_date_dim)

_DATE_COLS = {"date", "valid_from", "valid_to"}


def _coerce_dates(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if c in _DATE_COLS:
            df[c] = pd.to_datetime(df[c]).dt.date
    return df


def seed(client, verbose: bool = True) -> dict:
    items = [
        ("dim_source",        build_source_dim()),
        ("dim_country",       build_country_dim()),
        ("dim_indicator",     build_indicator_dim()),
        ("dim_disaster_type", build_disaster_dim()),
        ("dim_sector",        build_sector_dim()),
        ("dim_date",          build_date_dim()),
    ]
    counts = {}
    for table, df in items:
        df = _coerce_dates(df)
        client.insert_df(f"{DATABASE}.{table}", df)
        counts[table] = len(df)
        if verbose:
            print(f"  seeded {table:20} {len(df):>8,} rows")
    return counts


if __name__ == "__main__":
    from .db import get_client
    seed(get_client(database=DATABASE))
