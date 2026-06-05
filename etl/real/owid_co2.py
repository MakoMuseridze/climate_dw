"""OWID CO2 dataset -> fact_emissions_co2 (source_id 1).

Format: one row per (country, year); `iso_code` holds ISO3 for real countries
(aggregates use OWID_* codes which are dropped by the ISO3 join)."""
from __future__ import annotations
import pandas as pd
from .base import Extractor


class OwidCo2(Extractor):
    source_id = 1
    source_name = "OWID CO2 Data"
    target_table = "fact_emissions_co2"

    COLS = {
        "co2": "co2_mt", "co2_per_capita": "co2_per_capita_t",
        "co2_per_gdp": "co2_per_gdp_kg", "coal_co2": "coal_co2_mt",
        "oil_co2": "oil_co2_mt", "gas_co2": "gas_co2_mt",
        "cement_co2": "cement_co2_mt", "cumulative_co2": "cumulative_co2_mt",
        "share_global_co2": "share_global_co2",
    }

    def extract(self) -> pd.DataFrame:
        path = self.fetch(self.source_url, "owid-co2-data.csv")
        raw = pd.read_csv(path)
        raw = raw[raw["iso_code"].notna() & raw["co2"].notna()].copy()
        out = pd.DataFrame({"year": raw["year"]})
        out["country_id"] = self.resolver.map_iso3(raw["iso_code"])
        for src, dst in self.COLS.items():
            out[dst] = pd.to_numeric(raw.get(src), errors="coerce").fillna(0.0)
        out["source_id"] = self.source_id
        return out
