"""Gridded NetCDF/GeoTIFF -> country-level facts.

Shared spatial-aggregation helper plus extractors for gridded temperature and
precipitation. Requires: xarray, netCDF4, regionmask, geopandas, country_converter.

  HadCRUT5      (12) -> fact_temperature    (anomaly)
  NOAAGlobalTemp(11) -> fact_temperature    (anomaly)
  GPCC          (14) -> fact_precipitation  (mm/month)

Place downloaded files in data/raw/ (see each class's FILE_GLOB).
"""
from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd
from .base import Extractor


def aggregate_grid_to_country(da, resolver=None, *, agg: str = "mean",
                              target_deg: float = 1.0) -> pd.DataFrame:
    """Area-weighted aggregation of a gridded DataArray(time, lat, lon) to
    country level. Vectorized: coarsen to ~target_deg, mask once, then a single
    grouped cos(lat)-weighted reduction per country. Returns long df: iso3, date, value.
    """
    import regionmask
    import country_converter as coco

    # normalise coord names -> lat / lon
    ren = {}
    for c in list(da.dims):
        cl = c.lower()
        if cl in ("latitude", "lat"):
            ren[c] = "lat"
        elif cl in ("longitude", "lon"):
            ren[c] = "lon"
        elif cl in ("time", "valid_time", "date"):
            ren[c] = "time"
    da = da.rename(ren)
    # drop any extra dims (z / level / bnds / realization) -> keep (time, lat, lon)
    for d in [d for d in da.dims if d not in ("time", "lat", "lon")]:
        da = da.isel({d: 0}, drop=True)
    da = da.transpose("time", "lat", "lon")

    # coarsen fine grids (e.g. ERA5 0.25deg) to ~target_deg for speed/memory
    step = float(abs(da["lat"].values[1] - da["lat"].values[0]))
    if step and step < target_deg:
        f = max(1, int(round(target_deg / step)))
        da = da.coarsen(lat=f, lon=f, boundary="trim").mean()

    countries = regionmask.defined_regions.natural_earth_v5_0_0.countries_110
    mask2d = countries.mask(da)                                  # (lat, lon) region number, NaN outside
    lat = da["lat"].values
    w2d = (np.cos(np.deg2rad(lat))[:, None] * np.ones((1, da["lon"].size))).ravel()
    mv = mask2d.values.ravel()
    vals = da.values.reshape(da.sizes["time"], -1)               # (T, ncell)
    valid = ~np.isnan(mv)
    mv = mv[valid].astype(int); w = w2d[valid]; vals = vals[:, valid]

    times = pd.to_datetime(da["time"].values)
    dates = np.array([dt.date(t.year, t.month, 1) for t in times])

    # region number -> ISO3 via Natural Earth country names
    uniq = np.unique(mv)
    iso = coco.CountryConverter().convert([countries.names[r] for r in uniq],
                                          to="ISO3", not_found=None)
    iso = iso if isinstance(iso, list) else [iso]
    iso_by_region = dict(zip(uniq.tolist(), iso))

    frames = []
    for r in uniq:
        iso3 = iso_by_region.get(int(r))
        if not isinstance(iso3, str):
            continue
        sel = mv == r
        v = vals[:, sel]; wr = w[sel]                            # (T, nr), (nr,)
        finite = np.isfinite(v)
        num = np.nansum(np.where(finite, v, 0.0) * wr, axis=1)
        den = np.sum(np.where(finite, wr, 0.0), axis=1)
        ts = np.divide(num, den, out=np.full(num.shape, np.nan), where=den > 0)
        ok = np.isfinite(ts)
        if ok.any():
            frames.append(pd.DataFrame({"iso3": iso3, "date": dates[ok], "value": ts[ok]}))
    return (pd.concat(frames, ignore_index=True) if frames
            else pd.DataFrame(columns=["iso3", "date", "value"]))


class _GriddedBase(Extractor):
    FILE_GLOB: list = []
    VAR_CANDIDATES: tuple = ()

    def _open_var(self):
        import xarray as xr
        path = self.local_or_fetch(self.FILE_GLOB, None, None,
                                   hint=f"Download {self.source_name} NetCDF")
        ds = xr.open_dataset(path)
        var = next((v for v in self.VAR_CANDIDATES if v in ds.variables),
                   list(ds.data_vars)[0])
        return ds[var]


class HadCrut5(_GriddedBase):
    source_id = 12
    source_name = "HadCRUT5"
    target_table = "fact_temperature"
    FILE_GLOB = ["*HadCRUT*.nc", "*hadcrut*.nc"]
    VAR_CANDIDATES = ("tas_mean", "temperature_anomaly", "tas")

    def extract(self) -> pd.DataFrame:
        agg = aggregate_grid_to_country(self._open_var(), self.resolver)
        out = pd.DataFrame({"date": agg["date"],
                            "temp_anomaly_c": agg["value"].astype("float32"),
                            "temp_abs_c": pd.NA})
        out["country_id"] = self.resolver.map_iso3(agg["iso3"])
        out["source_id"] = self.source_id
        return out


class NoaaGlobalTemp(HadCrut5):
    source_id = 11
    source_name = "NOAAGlobalTemp"
    FILE_GLOB = ["*NOAAGlobalTemp*.nc", "*noaaglobaltemp*.nc"]
    VAR_CANDIDATES = ("anom", "temperature_anomaly", "tas")


class Gpcc(_GriddedBase):
    source_id = 14
    source_name = "GPCC"
    target_table = "fact_precipitation"
    FILE_GLOB = ["*GPCC*.nc", "*gpcc*.nc", "*precip*.nc", "*full_data*monthly*.nc"]
    VAR_CANDIDATES = ("precip", "p", "precipitation")

    def _open_var(self):
        """GPCC ships one file per decade; combine all matching .nc on time."""
        import xarray as xr, glob, os
        files = []
        for pat in self.FILE_GLOB:
            files += glob.glob(os.path.join(self.raw_dir, pat))
            files += glob.glob(os.path.join(self.raw_dir, "**", pat), recursive=True)
        files = sorted(set(files))
        if not files:
            self.local_or_fetch(self.FILE_GLOB, None, None,
                                hint="Download GPCC monthly NetCDF(s) and gunzip the .gz")
        ds0 = xr.open_dataset(files[0])
        var = next((v for v in self.VAR_CANDIDATES if v in ds0.variables), list(ds0.data_vars)[0])
        if len(files) == 1:
            return ds0[var]
        arrs = [xr.open_dataset(f)[var] for f in files]
        return xr.concat(arrs, dim="time").sortby("time")

    def extract(self) -> pd.DataFrame:
        agg = aggregate_grid_to_country(self._open_var(), self.resolver)
        out = pd.DataFrame({"date": agg["date"],
                            "precip_mm": agg["value"].astype("float32")})
        out["country_id"] = self.resolver.map_iso3(agg["iso3"])
        out["source_id"] = self.source_id
        return out
