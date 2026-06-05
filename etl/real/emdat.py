"""EM-DAT disaster database -> fact_disasters (source_id 5). GATED: requires a
free account at https://public.emdat.be/ . Export the xlsx and place it in
data/raw/ (e.g. emdat_public.xlsx).

Aggregates the event-level export to (country, year, disaster_type)."""
from __future__ import annotations
import pandas as pd
from .base import Extractor
from ..dimensions import DISASTER_TYPE_TO_ID


def _col(df, *cands):
    low = {str(c).strip().lower(): c for c in df.columns}
    for cand in cands:
        if cand.lower() in low:
            return low[cand.lower()]
    # fuzzy contains
    for cand in cands:
        for lc, orig in low.items():
            if cand.lower() in lc:
                return orig
    return None


class EmDat(Extractor):
    source_id = 5
    source_name = "EM-DAT"
    target_table = "fact_disasters"

    def extract(self) -> pd.DataFrame:
        path = self.local_or_fetch(["*emdat*.xlsx", "*EM-DAT*.xlsx", "*emdat*.csv"],
                                   None, None,
                                   hint="Register at public.emdat.be and export the xlsx")
        raw = (pd.read_excel(path) if path.lower().endswith((".xlsx", ".xls"))
               else pd.read_csv(path))
        iso = _col(raw, "ISO", "Country code", "iso3")
        year = _col(raw, "Year", "Start Year")
        dtype = _col(raw, "Disaster Type")
        deaths = _col(raw, "Total Deaths")
        affected = _col(raw, "Total Affected", "No. Affected", "Total affected")
        damage = _col(raw, "Total Damage ('000 US$)", "Total Damage, Adjusted ('000 US$)",
                      "Total Damage")
        df = pd.DataFrame({
            "iso3": raw[iso], "year": pd.to_numeric(raw[year], errors="coerce"),
            "dtype": raw[dtype].astype(str),
            "deaths": pd.to_numeric(raw.get(deaths), errors="coerce").fillna(0),
            "affected": pd.to_numeric(raw.get(affected), errors="coerce").fillna(0),
            "damage": pd.to_numeric(raw.get(damage), errors="coerce").fillna(0),
        }).dropna(subset=["year"])
        df["disaster_type_id"] = df["dtype"].map(DISASTER_TYPE_TO_ID)
        df = df.dropna(subset=["disaster_type_id"])   # drop unmapped (e.g. technological) types
        df["disaster_type_id"] = df["disaster_type_id"].astype(int)
        g = df.groupby(["iso3", "year", "disaster_type_id"], as_index=False).agg(
            events=("dtype", "size"), total_deaths=("deaths", "sum"),
            total_affected=("affected", "sum"), total_damage_usd_k=("damage", "sum"))
        g["country_id"] = self.resolver.map_iso3(g["iso3"])
        g["source_id"] = self.source_id
        return g[["country_id", "year", "disaster_type_id", "events", "total_deaths",
                  "total_affected", "total_damage_usd_k", "source_id"]]
