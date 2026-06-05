"""EDGAR GHG by sector & country -> fact_emissions_by_sector (source_id 6).

Recommended: "EDGAR Total GHG in CO2eq" = EDGAR_AR5_GHG_1970_2024.zip from
https://edgar.jrc.ec.europa.eu/dataset_ghg2025  -> drop the .zip in data/raw/.
The workbook has ~10 preamble rows; the real header (Country_code_A3, Y_1970..)
is detected automatically. The 'IPCC 2006' sector sheet is preferred.
Country totals are kton/year -> x0.001 -> Mt.
"""
from __future__ import annotations
import io
import re
import zipfile
import pandas as pd
from .base import Extractor

_IPCC_PREFIX = [("1a1", 1), ("1a2", 2), ("1a3", 3), ("1a4", 6), ("1a5", 6), ("1b", 1),
                ("2", 2), ("4a", 4), ("4b", 4), ("4c", 4), ("4d", 4), ("4f", 4),
                ("3", 4), ("5", 4), ("6", 5), ("7", 1)]
_KW = [("power", 1), ("energy", 1), ("combustion", 1), ("refiner", 1), ("fuel", 1),
       ("industr", 2), ("manufactur", 2), ("process", 2), ("cement", 2), ("mineral", 2),
       ("metal", 2), ("iron", 2), ("chemical", 2),
       ("transport", 3), ("aviation", 3), ("road", 3), ("ship", 3), ("rail", 3),
       ("agricultur", 4), ("enteric", 4), ("manure", 4), ("soil", 4), ("livestock", 4),
       ("waste", 5), ("landfill", 5), ("incinerat", 5), ("water", 5),
       ("building", 6), ("residential", 6)]


def _sector_id(name) -> int:
    n = str(name).lower().strip()
    for kw, sid in _KW:
        if kw in n:
            return sid
    flat = n.replace(" ", "")
    for pre, sid in _IPCC_PREFIX:
        if flat.startswith(pre):
            return sid
    return 7


def _gas(name) -> str:
    n = str(name).upper()
    for g in ("CO2", "CH4", "N2O"):
        if g in n:
            return g
    return "GHG"


class Edgar(Extractor):
    source_id = 6
    source_name = "EDGAR v8.0"
    target_table = "fact_emissions_by_sector"
    UNIT_SCALE = 0.001  # kton -> Mt

    def _read_table(self) -> pd.DataFrame:
        path = self.local_or_fetch(
            ["*EDGAR*GHG*.zip", "*EDGAR*.zip", "*EDGAR*.xlsx", "*edgar*.xlsx"],
            None, None,
            hint="Download EDGAR_AR5_GHG_1970_2024.zip from edgar.jrc.ec.europa.eu/dataset_ghg2025")
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as zf:
                name = next(n for n in zf.namelist() if n.lower().endswith((".xlsx", ".xls")))
                sheets = pd.read_excel(io.BytesIO(zf.read(name)), sheet_name=None, header=None)
        else:
            sheets = pd.read_excel(path, sheet_name=None, header=None)

        best, best_score = None, -1
        for raw in sheets.values():
            hdr = next((i for i in range(min(30, len(raw)))
                        if any(str(c).strip().lower() == "country_code_a3" for c in raw.iloc[i])), None)
            if hdr is None:
                continue
            cols = [str(c).strip() for c in raw.iloc[hdr]]
            nyear = sum(bool(re.fullmatch(r"Y_?\d{4}", c)) or c[:4].isdigit() for c in cols)
            has_sector = any("ipcc" in c.lower() and "name" in c.lower() for c in cols)
            score = nyear + (100 if has_sector else 0)
            if score > best_score:
                df = raw.iloc[hdr + 1:].copy()
                df.columns = cols
                best, best_score = df, score
        if best is None:
            raise ValueError("[EDGAR] no Country_code_A3 header found in any sheet")
        return best

    def extract(self) -> pd.DataFrame:
        raw = self._read_table()
        low = {str(c).lower(): c for c in raw.columns}
        iso = low["country_code_a3"]
        subs = next((low[k] for k in low if "substance" in k or k == "gas"), None)
        sect = (next((low[k] for k in low if "ipcc" in k and "name" in k), None)
                or next((low[k] for k in low if "ipcc" in k or "sector" in k), None))
        year_cols = [c for c in raw.columns
                     if re.fullmatch(r"Y_?\d{4}", str(c)) or str(c).strip().isdigit()]
        idv = [c for c in (iso, subs, sect) if c is not None]
        long = raw.melt(id_vars=idv, value_vars=year_cols, var_name="ycol", value_name="emis")
        long["year"] = long["ycol"].astype(str).str.extract(r"(\d{4})").astype(int)
        long["emis"] = pd.to_numeric(long["emis"], errors="coerce") * self.UNIT_SCALE
        long = long.dropna(subset=["emis"])
        out = pd.DataFrame({
            "year": long["year"],
            "sector_id": long[sect].map(_sector_id) if sect else 7,
            "gas": long[subs].map(_gas) if subs else "GHG",
            "emissions_mt_co2e": long["emis"].astype(float),
        })
        out["country_id"] = self.resolver.map_iso3(long[iso])
        out["source_id"] = self.source_id
        return out[["country_id", "year", "sector_id", "gas", "emissions_mt_co2e", "source_id"]]
