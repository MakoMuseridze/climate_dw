"""ERA5 reanalysis (Copernicus CDS) -> fact_temperature (source_id 13).

GATED + LARGE. Requires a free CDS account and ~/.cdsapirc credentials:
  https://cds.climate.copernicus.eu/  (register, accept the ERA5 licence)

Flow: cdsapi downloads ERA5 monthly-mean 2m temperature (NetCDF) -> xarray ->
area-weighted country aggregation -> anomaly vs 1951-1980 baseline.
The CDS request can queue for hours; run early (as the proposal schedules).
"""
from __future__ import annotations
import os
import pandas as pd
from .base import Extractor
from .gridded import aggregate_grid_to_country


class Era5(Extractor):
    source_id = 13
    source_name = "ERA5 Reanalysis"
    target_table = "fact_temperature"
    YEARS = list(range(1960, 2025))
    BASELINE = (1951, 1980)

    def _download(self) -> str:
        """Retrieve ERA5 monthly 2m temperature via the CDS API (cached)."""
        target = os.path.join(self.raw_dir, "era5_t2m_monthly.nc")
        if os.path.exists(target):
            return target
        import cdsapi
        c = cdsapi.Client()
        c.retrieve(
            "reanalysis-era5-single-levels-monthly-means",
            {
                "product_type": "monthly_averaged_reanalysis",
                "variable": "2m_temperature",
                "year": [str(y) for y in self.YEARS],
                "month": [f"{m:02d}" for m in range(1, 13)],
                "time": "00:00",
                "format": "netcdf",
            },
            target,
        )
        return target

    def extract(self) -> pd.DataFrame:
        import xarray as xr
        ds = xr.open_dataset(self._download())
        var = "t2m" if "t2m" in ds.variables else list(ds.data_vars)[0]
        da = ds[var] - 273.15  # K -> C
        agg = aggregate_grid_to_country(da, self.resolver, agg="mean")
        agg["year"] = pd.to_datetime(agg["date"]).dt.year
        # anomaly vs baseline climatology, per country-month
        agg["month"] = pd.to_datetime(agg["date"]).dt.month
        base = agg[(agg.year >= self.BASELINE[0]) & (agg.year <= self.BASELINE[1])]
        clim = base.groupby(["iso3", "month"])["value"].mean().rename("clim")
        agg = agg.merge(clim, on=["iso3", "month"], how="left")
        agg["anom"] = agg["value"] - agg["clim"]
        out = pd.DataFrame({"date": agg["date"],
                            "temp_anomaly_c": agg["anom"].astype("float32"),
                            "temp_abs_c": agg["value"].astype("float32")})
        out["country_id"] = self.resolver.map_iso3(agg["iso3"])
        out["source_id"] = self.source_id
        return out.dropna(subset=["temp_anomaly_c"])
