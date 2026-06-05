"""World Bank WDI (API) -> fact_socioeconomic (source_id 3).

Pulls the 25 indicators defined in etl.dimensions.INDICATORS via the v2 JSON
API (paginated). Result cached to data/raw/wdi_socioeconomic.parquet so reruns
don't re-hit the API."""
from __future__ import annotations
import os
import pandas as pd
from .base import Extractor
from ..dimensions import INDICATORS

API = ("https://api.worldbank.org/v2/country/all/indicator/{code}"
       "?format=json&per_page=20000&page={page}")


class WorldBankWDI(Extractor):
    source_id = 3
    source_name = "World Bank WDI"
    target_table = "fact_socioeconomic"

    def _pull_indicator(self, requests, code: str) -> list[tuple]:
        page, pages, recs = 1, 1, []
        while page <= pages:
            r = requests.get(API.format(code=code, page=page), timeout=120,
                             headers={"User-Agent": "climate-dw-etl/1.0"})
            r.raise_for_status()
            js = r.json()
            if not isinstance(js, list) or len(js) < 2 or js[1] is None:
                break
            pages = int(js[0].get("pages", 1))
            for d in js[1]:
                val, iso = d.get("value"), d.get("countryiso3code")
                if val is None or not iso:
                    continue
                try:
                    recs.append((iso, int(d["date"]), float(val)))
                except (ValueError, TypeError):
                    continue
            page += 1
        return recs

    def extract(self) -> pd.DataFrame:
        cache = os.path.join(self.raw_dir, "wdi_socioeconomic.parquet")
        if os.path.exists(cache):
            big = pd.read_parquet(cache)
        else:
            import requests
            frames = []
            for iid, code, *_ in INDICATORS:
                recs = self._pull_indicator(requests, code)
                if recs:
                    df = pd.DataFrame(recs, columns=["iso3", "year", "value"])
                    df["indicator_id"] = iid
                    frames.append(df)
            big = pd.concat(frames, ignore_index=True)
            big.to_parquet(cache, index=False)
        big["country_id"] = self.resolver.map_iso3(big["iso3"])
        big["source_id"] = self.source_id
        return big[["country_id", "indicator_id", "year", "value", "source_id"]]
