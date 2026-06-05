"""ND-GAIN Country Index -> fact_vulnerability (source_id 4).

Accepts either the downloaded ZIP or an unzipped `resources/` folder in
data/raw/. Reads the canonical gain / vulnerability / readiness wide CSVs
(ISO3, Name, <year columns>). Source:
https://gain.nd.edu/our-work/country-index/download-data/
"""
from __future__ import annotations
import os
import io
import glob
import zipfile
import pandas as pd
from .base import Extractor


def _melt_wide(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    iso_col = next((c for c in df.columns if str(c).strip().upper() in
                    ("ISO3", "ISO", "CODE", "ISO_A3")), df.columns[0])
    year_cols = [c for c in df.columns if str(c).strip().isdigit()]
    long = df.melt(id_vars=[iso_col], value_vars=year_cols,
                   var_name="year", value_name=value_name).rename(columns={iso_col: "iso3"})
    long["year"] = long["year"].astype(int)
    long[value_name] = pd.to_numeric(long[value_name], errors="coerce")
    return long.dropna(subset=[value_name])


class NdGain(Extractor):
    source_id = 4
    source_name = "ND-GAIN Index"
    target_table = "fact_vulnerability"

    def _find(self, key: str) -> str | None:
        """Find resources/<key>/<key>.csv, avoiding delta/trends/raw variants."""
        for pat in (f"resources/{key}/{key}.csv", f"**/{key}/{key}.csv", f"**/{key}.csv"):
            hits = sorted(glob.glob(os.path.join(self.raw_dir, pat), recursive=True))
            hits = [h for h in hits
                    if "delta" not in os.path.basename(h).lower()
                    and os.path.basename(h).lower() not in ("raw.csv", "raw0.csv", "input.csv", "score.csv")
                    and "/trends/" not in h.replace("\\", "/").lower()]
            if hits:
                return hits[0]
        return None

    def _read_components(self) -> dict:
        comp = {}
        zp = self.find_local("*nd*gain*.zip", "*gain*.zip", "resources.zip")
        if zp and not self._find("gain"):           # only unzip if not already extracted
            with zipfile.ZipFile(zp) as zf:
                for name in zf.namelist():
                    low = name.lower()
                    for key in ("gain", "vulnerability", "readiness"):
                        if f"{key}/{key}.csv" in low and key not in comp:
                            comp[key] = pd.read_csv(io.BytesIO(zf.read(name)))
        for key in ("gain", "vulnerability", "readiness"):
            if key not in comp:
                f = self._find(key)
                if f:
                    comp[key] = pd.read_csv(f)
        if "gain" not in comp:
            raise FileNotFoundError(
                "[ND-GAIN] place resources.zip (or the unzipped resources/ folder) in "
                "data/raw/ — https://gain.nd.edu/our-work/country-index/download-data/")
        return comp

    def extract(self) -> pd.DataFrame:
        comp = self._read_components()
        out = _melt_wide(comp["gain"], "nd_gain_index")
        for key, col in (("vulnerability", "vulnerability"), ("readiness", "readiness")):
            out = (out.merge(_melt_wide(comp[key], col), on=["iso3", "year"], how="left")
                   if key in comp else out.assign(**{col: 0.0}))
        out["country_id"] = self.resolver.map_iso3(out["iso3"])
        out["source_id"] = self.source_id
        return out[["country_id", "year", "nd_gain_index", "vulnerability", "readiness", "source_id"]]
