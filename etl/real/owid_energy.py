"""OWID Energy dataset -> fact_energy (source_id 2)."""
from __future__ import annotations
import pandas as pd
from .base import Extractor


class OwidEnergy(Extractor):
    source_id = 2
    source_name = "OWID Energy Data"
    target_table = "fact_energy"

    COLS = {
        "primary_energy_consumption": "primary_energy_twh",
        "fossil_share_energy": "fossil_share_pct",
        "renewables_share_energy": "renewables_share_pct",
        "nuclear_share_energy": "nuclear_share_pct",
        "low_carbon_share_energy": "low_carbon_share_pct",
        "electricity_demand": "electricity_demand_twh",
        "energy_per_capita": "energy_per_capita_kwh",
    }

    def extract(self) -> pd.DataFrame:
        path = self.fetch(self.source_url, "owid-energy-data.csv")
        raw = pd.read_csv(path)
        raw = raw[raw["iso_code"].notna() &
                  raw["primary_energy_consumption"].notna()].copy()
        out = pd.DataFrame({"year": raw["year"]})
        out["country_id"] = self.resolver.map_iso3(raw["iso_code"])
        for src, dst in self.COLS.items():
            out[dst] = pd.to_numeric(raw.get(src), errors="coerce").fillna(0.0)
        out["source_id"] = self.source_id
        return out
