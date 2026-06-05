"""Climate TRACE country-level emissions -> fact_emissions_by_sector
(source_id 16). Download country CSVs from https://climatetrace.org/data and
place in data/raw/. Emissions assumed in tonnes CO2e (-> Mt)."""
from __future__ import annotations
import re
import pandas as pd
from .base import Extractor
from .edgar import _sector_id, _gas


class ClimateTrace(Extractor):
    source_id = 16
    source_name = "Climate TRACE"
    target_table = "fact_emissions_by_sector"

    def extract(self) -> pd.DataFrame:
        path = self.local_or_fetch(["*climate*trace*.csv", "*climatetrace*.csv"],
                                   None, None,
                                   hint="Download country emissions CSV from climatetrace.org/data")
        raw = pd.read_csv(path)
        cols = {c.lower().strip(): c for c in raw.columns}
        iso = next((cols[k] for k in cols if k in ("country", "iso3", "iso3_country")), None)
        sect = next((cols[k] for k in cols if "sector" in k), None)
        gas = next((cols[k] for k in cols if k == "gas"), None)
        emis = next((cols[k] for k in cols if "emission" in k), None)
        ytime = next((cols[k] for k in cols if k in ("year", "start_time", "start_year")), None)
        year = (pd.to_datetime(raw[ytime], errors="coerce").dt.year
                if "time" in str(ytime).lower() else pd.to_numeric(raw[ytime], errors="coerce"))
        out = pd.DataFrame({
            "year": year,
            "sector_id": raw[sect].map(_sector_id) if sect else 7,
            "gas": raw[gas].map(_gas) if gas else "CO2",
            "emissions_mt_co2e": pd.to_numeric(raw[emis], errors="coerce") / 1e6,
        }).dropna(subset=["year", "emissions_mt_co2e"])
        out["country_id"] = self.resolver.map_iso3(raw.loc[out.index, iso])
        out["source_id"] = self.source_id
        return out[["country_id", "year", "sector_id", "gas", "emissions_mt_co2e", "source_id"]]
