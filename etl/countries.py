"""Country-code harmonization: map any source's country labels to the
warehouse surrogate `country_id` via ISO3.

Sources name countries inconsistently ("Russia" vs "Russian Federation" vs
"RUS" vs "643"). We normalize everything to ISO3 with country_converter,
then look up country_id from dim_country.
"""
from __future__ import annotations
import pandas as pd


class CountryResolver:
    def __init__(self, client):
        df = client.query_df(
            "SELECT country_id, toString(iso3) AS iso3 FROM climate.dim_country WHERE is_current = 1")

        def _s(v):
            if isinstance(v, (bytes, bytearray)):
                v = v.decode("ascii", "ignore")
            return str(v).strip().strip("\x00").upper()

        self.iso3_to_id = {_s(r.iso3): int(r.country_id) for r in df.itertuples()}
        import country_converter as coco
        self.cc = coco.CountryConverter()
        self.unmatched: set[str] = set()

    # ---- ISO3 already present in the source ----
    def map_iso3(self, s: pd.Series) -> pd.Series:
        ids = s.astype(str).str.strip().str.upper().map(self.iso3_to_id)
        self._record_unmatched(s, ids)
        return ids

    # ---- arbitrary names / codes -> ISO3 -> id ----
    def map_names(self, s: pd.Series) -> pd.Series:
        uniq = s.dropna().astype(str).str.strip().unique().tolist()
        iso = self.cc.convert(uniq, to="ISO3", not_found=None)
        if not isinstance(iso, list):
            iso = [iso]
        name_to_iso = dict(zip(uniq, iso))
        ids = (s.astype(str).str.strip().map(name_to_iso)
                .map(lambda x: self.iso3_to_id.get(x) if isinstance(x, str) else None))
        self._record_unmatched(s, ids)
        return ids

    def _record_unmatched(self, src: pd.Series, ids: pd.Series) -> None:
        miss = src[ids.isna()].astype(str).str.strip().unique().tolist()
        self.unmatched.update(m for m in miss if m and m.lower() != "nan")

    def report(self) -> str:
        if not self.unmatched:
            return "all country labels matched"
        sample = sorted(self.unmatched)[:15]
        return f"{len(self.unmatched)} unmatched labels (sample: {sample})"
