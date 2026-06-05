"""Global Carbon Budget national territorial emissions -> fact_emissions_co2
(source_id 8), kept alongside OWID (source_id 1) for cross-source reconciliation.

GCB 'National_Fossil_Carbon_Emissions_*.xlsx', sheet 'Territorial Emissions':
~9 preamble rows, then a row of COUNTRY names as columns and YEARS down column A.
Values are million tonnes of CARBON (MtC) -> x3.664 -> Mt CO2.
Download from https://globalcarbonbudget.org/ ; place the xlsx in data/raw/.
"""
from __future__ import annotations
import pandas as pd
from .base import Extractor

C_TO_CO2 = 3.664


def _is_year(v) -> bool:
    try:
        return 1700 <= int(float(v)) <= 2100
    except (ValueError, TypeError):
        return False


class GlobalCarbonBudget(Extractor):
    source_id = 8
    source_name = "Global Carbon Budget"
    target_table = "fact_emissions_co2"
    DOWNLOAD_URL = None

    def extract(self) -> pd.DataFrame:
        path = self.local_or_fetch(
            ["*National_Fossil*.xlsx", "*National*Carbon*Emissions*.xlsx",
             "*Global_Carbon_Budget*.xlsx", "*GCB*.xlsx"],
            self.DOWNLOAD_URL, "gcb_national_fossil.xlsx",
            hint="Download the National Fossil Carbon Emissions xlsx from globalcarbonbudget.org")
        xl = pd.ExcelFile(path)
        sheet = next((s for s in xl.sheet_names if "territorial" in s.lower()), xl.sheet_names[0])
        raw = xl.parse(sheet, header=None)

        data_start = next((i for i in range(len(raw)) if _is_year(raw.iloc[i, 0])), None)
        if data_start is None:
            raise ValueError(f"[GCB] no year column found in sheet '{sheet}'")
        # country header = row just above the data with the most text cells (prefer closest)
        cand = range(max(0, data_start - 4), data_start)
        hdr = max(cand, key=lambda i: (int(raw.iloc[i, 1:].notna().sum()), i))
        names = raw.iloc[hdr].tolist()
        cols = {j: str(names[j]).strip() for j in range(1, len(names))
                if isinstance(names[j], str) and names[j].strip()
                and names[j].strip().lower() != "nan"}

        block = raw.iloc[data_start:, [0] + list(cols)].copy()
        block.columns = ["Year"] + [cols[j] for j in cols]
        block = block[pd.to_numeric(block["Year"], errors="coerce").notna()]
        long = block.melt(id_vars="Year", var_name="country", value_name="mtc")
        long["mtc"] = pd.to_numeric(long["mtc"], errors="coerce")
        long = long.dropna(subset=["mtc"])

        out = pd.DataFrame({
            "year": long["Year"].astype(float).astype(int),
            "co2_mt": long["mtc"].astype(float) * C_TO_CO2,
        })
        out["country_id"] = self.resolver.map_names(long["country"])
        for c in ("co2_per_capita_t", "co2_per_gdp_kg", "coal_co2_mt", "oil_co2_mt",
                  "gas_co2_mt", "cement_co2_mt", "cumulative_co2_mt", "share_global_co2"):
            out[c] = 0.0
        out["source_id"] = self.source_id
        return out
