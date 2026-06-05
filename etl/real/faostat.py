"""FAOSTAT (normalized) -> fact_agriculture (source_id 7).

Accepts a single normalized CSV, a single-domain zip, OR the big "bulk by
group" bundle (e.g. FAOSTAT_A-S_E.zip) which is a zip-of-zips; in that case a
climate-relevant domain is picked automatically. Normalized files have columns:
Area, Item, Element, Year, Unit, Value. From https://bulks-faostat.fao.org/production/
"""
from __future__ import annotations
import io
import zipfile
import pandas as pd
from .base import Extractor

# preferred domains when reading the big A-S / T-Z bundle (smaller + climate-relevant first)
_PREF = ["emissions_totals", "environment_emissions_by_sector", "emissions_crops",
         "emissions_livestock", "land_use", "inputs_landuse", "production_crops"]


def _read_csv_bytes(b: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(b), encoding="latin-1")


class Faostat(Extractor):
    source_id = 7
    source_name = "FAOSTAT"
    target_table = "fact_agriculture"

    @staticmethod
    def _prefer(paths):
        import os
        for p in _PREF:
            hit = next((x for x in sorted(paths) if p in os.path.basename(x).lower()), None)
            if hit:
                return hit
        return sorted(paths)[0] if paths else None

    def _read(self) -> pd.DataFrame:
        import glob, os
        rd = self.raw_dir
        # 1) loose normalized CSV(s) (fully unzipped) -> prefer climate-relevant domain
        csvs = (glob.glob(os.path.join(rd, "**", "*_All_Data_*.csv"), recursive=True)
                + glob.glob(os.path.join(rd, "*FAOSTAT*.csv")))
        pick = self._prefer(csvs)
        if pick:
            return pd.read_csv(pick, encoding="latin-1")
        # 2) loose single-domain zips (bundle unzipped to the 71 domain zips)
        dzips = [x for x in glob.glob(os.path.join(rd, "**", "*_All_Data_*.zip"), recursive=True)]
        pick = self._prefer(dzips)
        if pick:
            with zipfile.ZipFile(pick) as zf:
                c = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
                return _read_csv_bytes(zf.read(c))
        # 3) the big group bundle (zip-of-zips), e.g. FAOSTAT_A-S_E.zip
        zp = self.find_local("*FAOSTAT*.zip", "*faostat*.zip")
        if zp:
            with zipfile.ZipFile(zp) as zf:
                nested = [n for n in zf.namelist() if n.lower().endswith(".zip")]
                chosen = self._prefer(nested)
                if chosen:
                    with zipfile.ZipFile(io.BytesIO(zf.read(chosen))) as zf2:
                        c2 = next(n for n in zf2.namelist() if n.lower().endswith(".csv"))
                        return _read_csv_bytes(zf2.read(c2))
        raise FileNotFoundError(
            "[FAOSTAT] place a normalized bulk csv/zip in data/raw/ "
            "(https://bulks-faostat.fao.org/production/)")

    def extract(self) -> pd.DataFrame:
        raw = self._read()
        cols = {c.lower().strip(): c for c in raw.columns}
        area = cols.get("area") or cols.get("area name") or cols.get("country")
        item = cols.get("item") or cols.get("item name")
        element = cols.get("element") or cols.get("element name")
        year = cols.get("year")
        value = cols.get("value")
        unit = cols.get("unit")
        df = pd.DataFrame({
            "year": pd.to_numeric(raw[year], errors="coerce"),
            "item": raw[item].astype(str) if item else "",
            "element": raw[element].astype(str) if element else "",
            "value": pd.to_numeric(raw[value], errors="coerce"),
            "unit": raw[unit].astype(str) if unit else "",
        }).dropna(subset=["year", "value"])
        df["country_id"] = self.resolver.map_names(raw.loc[df.index, area])
        df["source_id"] = self.source_id
        return df[["country_id", "year", "item", "element", "value", "unit", "source_id"]]
