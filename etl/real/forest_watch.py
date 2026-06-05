"""Global Forest Watch country tree-cover loss -> fact_agriculture
(source_id 17; item='Forest land', element='Tree cover loss'). Download the
country CSV from https://www.globalforestwatch.org/ (or GFW API) into data/raw/.
Typically wide: country, then tc_loss_ha_2001 ... tc_loss_ha_2024."""
from __future__ import annotations
import re
import pandas as pd
from .base import Extractor


class ForestWatch(Extractor):
    source_id = 17
    source_name = "Global Forest Watch"
    target_table = "fact_agriculture"

    def extract(self) -> pd.DataFrame:
        path = self.local_or_fetch(["*forest*watch*.csv", "*gfw*.csv", "*treecover*loss*.csv"],
                                   None, None,
                                   hint="Download country tree-cover-loss CSV from globalforestwatch.org")
        raw = pd.read_csv(path)
        cols = {c.lower().strip(): c for c in raw.columns}
        iso = next((cols[k] for k in cols if k in ("iso", "iso3", "country", "country_iso")), None)
        loss_cols = [c for c in raw.columns if re.search(r"loss.*\d{4}|\d{4}.*loss", str(c).lower())]
        if loss_cols:
            long = raw.melt(id_vars=[iso], value_vars=loss_cols,
                            var_name="ycol", value_name="value")
            long["year"] = long["ycol"].astype(str).str.extract(r"(\d{4})").astype(float)
        else:  # already long
            ycol = next((cols[k] for k in cols if k == "year"), None)
            vcol = next((cols[k] for k in cols if "loss" in k or "value" in k), None)
            long = raw.rename(columns={ycol: "year", vcol: "value"})[[iso, "year", "value"]]
        long = long.dropna(subset=["year"])
        out = pd.DataFrame({
            "year": long["year"].astype(int), "item": "Forest land",
            "element": "Tree cover loss",
            "value": pd.to_numeric(long["value"], errors="coerce"), "unit": "ha",
        }).dropna(subset=["value"])
        out["country_id"] = self.resolver.map_iso3(long.loc[out.index, iso])
        out["source_id"] = self.source_id
        return out[["country_id", "year", "item", "element", "value", "unit", "source_id"]]
