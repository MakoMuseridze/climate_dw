"""NASA GISTEMP global land-ocean monthly anomaly -> fact_temperature
(country_id 0 = global, source_id 10).

GLB.Ts+dSST.csv: line 1 is a title (skipped), row 2 is the header
(Year, Jan..Dec, J-D, ...). Missing months are '***'. Values are vs the
1951-1980 baseline; some published versions use hundredths of degC, so the
scale is auto-detected."""
from __future__ import annotations
import datetime as dt
import pandas as pd
from .base import Extractor

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


class Gistemp(Extractor):
    source_id = 10
    source_name = "NASA GISTEMP v4"
    target_table = "fact_temperature"

    def extract(self) -> pd.DataFrame:
        path = self.fetch(self.source_url, "gistemp_GLB.Ts+dSST.csv")
        raw = pd.read_csv(path, skiprows=1)
        raw = raw.replace({r"^\*+$": None}, regex=True)
        long = raw.melt(id_vars="Year", value_vars=list(_MONTHS),
                        var_name="mon", value_name="val")
        long["val"] = pd.to_numeric(long["val"], errors="coerce")
        long = long.dropna(subset=["val"])
        # auto-detect hundredths-of-degree encoding
        scale = 0.01 if long["val"].abs().median() > 10 else 1.0
        out = pd.DataFrame({
            "country_id": 0,
            "date": [dt.date(int(y), _MONTHS[m], 1)
                     for y, m in zip(long["Year"], long["mon"])],
            "temp_anomaly_c": (long["val"] * scale).astype("float32"),
            "temp_abs_c": pd.NA,
            "source_id": self.source_id,
        })
        return out.sort_values("date").reset_index(drop=True)
