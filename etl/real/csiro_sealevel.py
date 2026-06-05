"""CSIRO global mean sea level reconstruction -> fact_sea_level (source_id 15).

Download a GMSL reconstruction CSV (values in mm) and drop it in data/raw/.
Recommended: CSIRO_Recons_gmsl_mo_2015.csv (monthly) — from
https://www.cmar.csiro.au/sealevel/sl_data_cmar.html  or
https://datahub.io/core/sea-level-rise

Robust to: comma/space/tab delimiters, a header row or none, and a time column
that is either a decimal year (1993.04) or a date string (1993-01-15).
"""
from __future__ import annotations
import datetime as dt
import pandas as pd
from .base import Extractor


class CsiroSeaLevel(Extractor):
    source_id = 15
    source_name = "CSIRO Sea Level"
    target_table = "fact_sea_level"
    DOWNLOAD_URL = None

    def extract(self) -> pd.DataFrame:
        path = self.local_or_fetch(
            ["*gmsl*.csv", "*gmsl*.txt", "*CSIRO_Recons*.csv", "*sea*level*.csv",
             "*sea_level*.txt", "*church_white*.txt", "*CSIRO*sea*"],
            self.DOWNLOAD_URL, "csiro_gmsl.csv",
            hint="Download a GMSL reconstruction CSV (mm) from cmar.csiro.au/sealevel/")

        # auto-detect delimiter + header
        raw = pd.read_csv(path, sep=None, engine="python", comment="#")
        if raw.shape[1] == 1:                      # whitespace file read as one column
            raw = pd.read_csv(path, sep=r"\s+", engine="python", comment="#", header=None)
        cols = {str(c).lower(): c for c in raw.columns}
        tcol = next((cols[k] for k in cols if any(w in k for w in ("time", "year", "date"))),
                    raw.columns[0])
        vcol = next((cols[k] for k in cols if "gmsl" in k or "sea level" in k or "level" in k),
                    raw.columns[1] if raw.shape[1] > 1 else raw.columns[0])
        ucol = next((cols[k] for k in cols if any(w in k for w in ("uncert", "error", "sigma"))), None)

        t = raw[tcol]
        tnum = pd.to_numeric(t, errors="coerce")
        if tnum.notna().mean() > 0.8:              # decimal year
            yr = tnum.astype("Int64")
            mo = (((tnum - tnum.astype(int)) * 12).clip(0, 11).astype("Int64") + 1)
            dates = [dt.date(int(y), int(m), 1) if pd.notna(y) else None for y, m in zip(yr, mo)]
        else:                                      # date string
            dd = pd.to_datetime(t, errors="coerce")
            dates = [dt.date(d.year, d.month, 1) if pd.notna(d) else None for d in dd]

        out = pd.DataFrame({
            "date": dates,
            "gmsl_mm": pd.to_numeric(raw[vcol], errors="coerce"),
            "gmsl_uncertainty_mm": (pd.to_numeric(raw[ucol], errors="coerce") if ucol else 0.0),
            "source_id": self.source_id,
        }).dropna(subset=["date", "gmsl_mm"])
        return out.groupby("date", as_index=False).first()
