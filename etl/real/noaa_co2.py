"""NOAA GML Mauna Loa monthly CO2 -> fact_co2_atmospheric (source_id 9).

co2_mm_mlo.txt: '#'-comment header, whitespace-delimited columns
  year  month  decimal_date  average  deseasonalized  ndays  sdev  unc
Missing values are -99.99."""
from __future__ import annotations
import datetime as dt
import pandas as pd
from .base import Extractor


class NoaaCo2(Extractor):
    source_id = 9
    source_name = "NOAA GML CO2"
    target_table = "fact_co2_atmospheric"

    def extract(self) -> pd.DataFrame:
        path = self.fetch(self.source_url, "co2_mm_mlo.txt")
        raw = pd.read_csv(path, sep=r"\s+", comment="#", header=None)
        ncol = raw.shape[1]
        year = raw[0].astype(int)
        month = raw[1].astype(int)
        average = pd.to_numeric(raw[3], errors="coerce")
        trend = pd.to_numeric(raw[4], errors="coerce") if ncol > 4 else average
        out = pd.DataFrame({
            "date": [dt.date(int(y), int(m), 1) for y, m in zip(year, month)],
            "station": "Mauna Loa",
            "co2_ppm": average,
            "co2_trend_ppm": trend,
            "source_id": self.source_id,
        })
        return out[out["co2_ppm"] > 0].reset_index(drop=True)
