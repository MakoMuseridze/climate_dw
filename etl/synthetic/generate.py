"""
TEST FIXTURE — synthetic data generator (NOT production data).

This module is used ONLY by scripts/validate_local.py for the offline
self-test. It is NOT part of the real-data ETL pipeline in etl/real/, and
none of the 15 loaded production sources originate here. Its sole purpose is
to let anyone exercise the full schema, materialized views, query library and
data-quality suite without Docker, a ClickHouse server, or any gated downloads.

Produces realistic, internally-consistent demo data across every dimension
and fact table (~800k fact rows) so the warehouse is fully demonstrable and
benchmarkable WITHOUT waiting on the gated real-world downloads (ERA5/CDS,
EM-DAT, Earthdata). Real ETL (etl/real/) drops into the same schema later.

Design notes
------------
* Country list & ISO3/region come from `country_converter` (real codes).
* Income group drives a per-country "development level" that ties GDP,
  population, energy and emissions together so cross-domain queries
  (e.g. emissions-vs-GDP) show genuine correlations.
* Global signals are physically plausible: temperature anomaly rises
  ~ -0.2C (1950) -> +1.1C (2024); Mauna Loa CO2 315 -> ~422 ppm; sea level
  rises monotonically with noise.
* Reproducible: fixed RNG seed.

Output: Parquet files in data/staging/synthetic/<table>.parquet
        (one per table; column order matches the INSERT column list).

Usage:  python -m etl.synthetic.generate            # writes parquet
        python -m etl.synthetic.generate --rows     # just print row counts
"""
from __future__ import annotations
import os
import sys
import argparse
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from etl.sources import SOURCES  # noqa: E402

OUT_DIR = os.path.join(REPO, "data", "staging", "synthetic")
SEED = 42
SYNTH = 99  # synthetic source_id

# Annual / monthly coverage windows
Y0, Y1 = 1960, 2024
YEARS = np.arange(Y0, Y1 + 1)
MONTH_Y0 = 1960

rng = np.random.default_rng(SEED)

# Countries whose scale we nudge so dashboards look plausible (pop_mult, gdp_pc_mult)
_BIG = {
    "CHN": (14.0, 0.9), "IND": (14.0, 0.35), "USA": (3.3, 6.0), "IDN": (2.7, 0.55),
    "PAK": (2.2, 0.25), "BRA": (2.1, 0.9), "NGA": (2.0, 0.25), "BGD": (1.6, 0.3),
    "RUS": (1.4, 1.2), "JPN": (1.25, 4.2), "DEU": (0.83, 4.8), "GBR": (0.67, 4.5),
    "FRA": (0.65, 4.4), "ITA": (0.60, 3.6), "KOR": (0.51, 3.5),
}

# Income classification sets (ISO3). Everything else defaults to Lower-middle.
_HIGH = set("USA CAN GBR FRA DEU ITA ESP NLD BEL AUT CHE SWE NOR DNK FIN IRL ISL LUX "
            "PRT GRC JPN KOR AUS NZL SGP ISR ARE QAT KWT BHR OMN SAU BRN HKG TWN CYP MLT "
            "SVN CZE EST LVA LTU SVK POL HRV HUN CHL URY PAN".split())
_UPPER = set("CHN RUS BRA MEX TUR ARG ZAF MYS THA KAZ COL PER ROU BGR SRB BLR GEO ARM AZE "
             "MKD MNE BIH ALB CRI DOM ECU PRY JAM BWA GAB NAM MUS LBN IRQ IRN JOR DZA "
             "CUB GTM".split())
_LOW = set("AFG ETH COD MLI NER TCD SOM SSD UGA RWA MWI MOZ BFA BDI GIN GNB LBR SLE TGO "
           "MDG CAF YEM SDN ERI GMB COG".split())


def _income(iso3: str) -> str:
    if iso3 in _HIGH:
        return "High income"
    if iso3 in _UPPER:
        return "Upper-middle income"
    if iso3 in _LOW:
        return "Low income"
    return "Lower-middle income"


_DEV = {"High income": 0.90, "Upper-middle income": 0.62,
        "Lower-middle income": 0.40, "Low income": 0.20}


# ---------------------------------------------------------------- dimensions
def build_countries() -> pd.DataFrame:
    import country_converter as coco
    data = coco.CountryConverter().data
    cols = data[["ISO3", "ISO2", "name_short", "continent", "UNregion"]].copy()
    cols = cols[cols["ISO3"].str.match(r"^[A-Z]{3}$", na=False)]
    # keep sovereign-ish set: drop tiny territories by excluding a few markers
    cols = cols[~cols["name_short"].str.contains(
        "Islands|Antarctica|Bouvet|Heard|Minor|Svalbard|Pitcairn|Tokelau|Niue|Wallis|"
        "French Southern|British Indian|Norfolk|Cocos|Christmas|Guernsey|Jersey|Faroe|"
        "Falkland|Vatican|Saint Helena|Mayotte|Aland Is|Åland", case=False, na=False)]
    cols = cols.drop_duplicates("ISO3").reset_index(drop=True)

    rows = []
    rows.append(dict(country_id=0, iso3="WLD", iso2="WD", country_name="World",
                     region="World", subregion="World", continent="World",
                     income_group="Aggregate", un_member=0, area_km2=148940000.0,
                     valid_from="1900-01-01", valid_to="2200-01-01", is_current=1))
    for i, r in enumerate(cols.itertuples(index=False), start=1):
        rows.append(dict(
            country_id=i, iso3=r.ISO3,
            iso2=(r.ISO2 if isinstance(r.ISO2, str) and len(r.ISO2) == 2 else "XX"),
            country_name=str(r.name_short),
            region=str(r.continent), subregion=str(r.UNregion), continent=str(r.continent),
            income_group=_income(r.ISO3), un_member=1,
            area_km2=float(rng.uniform(2000, 9_000_000)),
            valid_from="1900-01-01", valid_to="2200-01-01", is_current=1))
    return pd.DataFrame(rows)


def build_indicators() -> pd.DataFrame:
    specs = [
        (1,  "NY.GDP.MKTP.CD",     "GDP (current US$)",                 "USD",        "Economy"),
        (2,  "SP.POP.TOTL",        "Population, total",                 "persons",    "Demographics"),
        (3,  "NY.GDP.PCAP.CD",     "GDP per capita (current US$)",      "USD",        "Economy"),
        (4,  "SP.URB.TOTL.IN.ZS",  "Urban population (% of total)",     "%",          "Demographics"),
        (5,  "SP.DYN.LE00.IN",     "Life expectancy at birth",          "years",      "Health"),
        (6,  "EG.ELC.ACCS.ZS",     "Access to electricity (% pop)",     "%",          "Energy"),
        (7,  "EN.ATM.CO2E.PC",     "CO2 emissions per capita",          "t",          "Environment"),
        (8,  "NV.AGR.TOTL.ZS",     "Agriculture, value added (% GDP)",  "%",          "Economy"),
        (9,  "SL.UEM.TOTL.ZS",     "Unemployment (% labor force)",      "%",          "Economy"),
        (10, "SE.XPD.TOTL.GD.ZS",  "Govt education expenditure (% GDP)", "%",         "Education"),
        (11, "SP.DYN.TFRT.IN",     "Fertility rate, total",             "births/woman", "Demographics"),
        (12, "EN.POP.DNST",        "Population density",                 "people/km2", "Demographics"),
        (13, "NE.EXP.GNFS.ZS",     "Exports of goods/services (% GDP)", "%",          "Economy"),
        (14, "FP.CPI.TOTL.ZG",     "Inflation, consumer prices",        "%",          "Economy"),
        (15, "SH.XPD.CHEX.GD.ZS",  "Health expenditure (% GDP)",        "%",          "Health"),
        (16, "EG.USE.PCAP.KG.OE",  "Energy use per capita",             "kg oil eq",  "Energy"),
        (17, "AG.LND.FRST.ZS",     "Forest area (% land)",              "%",          "Environment"),
        (18, "ER.H2O.FWTL.ZS",     "Freshwater withdrawal (% resources)", "%",        "Environment"),
        (19, "IT.NET.USER.ZS",     "Individuals using internet (%)",    "%",          "Technology"),
        (20, "SI.POV.GINI",        "Gini index",                        "index",      "Inequality"),
        (21, "GC.DOD.TOTL.GD.ZS",  "Govt debt (% GDP)",                 "%",          "Economy"),
        (22, "SP.RUR.TOTL.ZS",     "Rural population (% of total)",     "%",          "Demographics"),
        (23, "EG.FEC.RNEW.ZS",     "Renewable energy consumption (%)",  "%",          "Energy"),
        (24, "AG.LND.ARBL.ZS",     "Arable land (% land)",              "%",          "Agriculture"),
        (25, "SH.STA.MMRT",        "Maternal mortality ratio",          "per 100k",   "Health"),
    ]
    return pd.DataFrame([dict(indicator_id=i, indicator_code=c, indicator_name=n,
                              unit=u, theme=t, source="World Bank WDI")
                         for (i, c, n, u, t) in specs])


def build_disaster_types() -> pd.DataFrame:
    rows = [
        (1, "Natural", "Hydrological",   "Flood",               "Riverine flood"),
        (2, "Natural", "Meteorological", "Storm",               "Tropical cyclone"),
        (3, "Natural", "Climatological", "Drought",             ""),
        (4, "Natural", "Climatological", "Wildfire",            "Forest fire"),
        (5, "Natural", "Geophysical",    "Earthquake",          "Ground movement"),
        (6, "Natural", "Meteorological", "Extreme temperature", "Heat wave"),
        (7, "Natural", "Hydrological",   "Landslide",           ""),
        (8, "Natural", "Biological",     "Epidemic",            "Viral disease"),
    ]
    return pd.DataFrame([dict(disaster_type_id=i, disaster_group=g, disaster_subgroup=sg,
                              disaster_type=t, disaster_subtype=st) for (i, g, sg, t, st) in rows])


def build_sectors() -> pd.DataFrame:
    rows = [(1, "Energy", "1A"), (2, "Industry", "2"), (3, "Transport", "1A3"),
            (4, "Agriculture", "3"), (5, "Waste", "4"), (6, "Buildings", "1A4")]
    return pd.DataFrame([dict(sector_id=i, sector_name=n, ipcc_code=c) for (i, n, c) in rows])


def build_sources() -> pd.DataFrame:
    return pd.DataFrame([dict(source_id=s["source_id"], source_name=s["source_name"],
                              domain=s["domain"], format=s["format"], url=s["url"],
                              license=s["license"], coverage=s["coverage"]) for s in SOURCES])


def build_dim_date() -> pd.DataFrame:
    d = pd.date_range("1900-01-01", "2024-12-31", freq="D")
    return pd.DataFrame(dict(
        date=d.date, year=d.year.astype("uint16"), month=d.month.astype("uint8"),
        day=d.day.astype("uint8"), quarter=d.quarter.astype("uint8"),
        decade=((d.year // 10) * 10).astype("uint16"),
        day_of_year=d.dayofyear.astype("uint16"),
        month_name=d.strftime("%B"),
        is_year_start=((d.month == 1) & (d.day == 1)).astype("uint8"),
        is_month_start=(d.day == 1).astype("uint8")))


# ---------------------------------------------------------------- facts
def build_facts(countries: pd.DataFrame):
    """Return dict[table_name] -> DataFrame. Country 0 (World) excluded from
    per-country facts; used only for global temperature series."""
    cc = countries[countries.country_id > 0].copy().reset_index(drop=True)
    n = len(cc)
    dev = cc["income_group"].map(_DEV).to_numpy() + rng.normal(0, 0.03, n)
    dev = np.clip(dev, 0.1, 0.97)

    # base population (1960) and gdp per capita (1960)
    pop0 = np.exp(rng.normal(15.5, 1.1, n)) * (0.4 + dev)          # ~ up to tens of millions
    gdp_pc0 = 300 + dev * 8000 * (0.5 + rng.random(n))            # USD
    for k, (pm, gm) in _BIG.items():
        idx = cc.index[cc.iso3 == k]
        if len(idx):
            j = idx[0]; pop0[j] *= pm; gdp_pc0[j] *= gm

    yr = YEARS
    ny = len(yr)
    t = (yr - Y0) / (Y1 - Y0)                                      # 0..1 over period

    # broadcast to (n, ny)
    pop_growth = (1 + (0.025 - 0.015 * dev))[:, None] ** np.arange(ny)[None, :]
    population = (pop0[:, None] * pop_growth).round()
    gdp_pc = gdp_pc0[:, None] * (1 + 0.02 + 0.015 * dev[:, None]) ** np.arange(ny)[None, :]
    gdp_pc *= (1 + rng.normal(0, 0.05, (n, ny)))
    gdp_total = gdp_pc * population

    # CO2: per-capita driven (realistic ~0.1-40 t/capita), tonnes -> Mt
    co2pc = ((0.4 + 13.0 * dev)[:, None]
             * (0.55 + 0.5 * t[None, :])
             * (1 + rng.normal(0, 0.05, (n, ny))))
    co2pc = np.clip(co2pc, 0.05, 60.0)
    co2_mt = np.clip(co2pc * population / 1e6, 0.001, None)        # million tonnes

    cid = cc["country_id"].to_numpy()
    cid_rep = np.repeat(cid, ny)
    yr_rep = np.tile(yr, n)

    out = {}

    # --- fact_emissions_co2
    co2_flat = co2_mt.ravel()
    pop_flat = population.ravel()
    gdp_flat = gdp_total.ravel()
    coal = co2_flat * rng.uniform(0.25, 0.45, co2_flat.size)
    oil = co2_flat * rng.uniform(0.25, 0.40, co2_flat.size)
    gas = co2_flat * rng.uniform(0.12, 0.25, co2_flat.size)
    cement = np.clip(co2_flat - coal - oil - gas, 0, None)
    cum = np.cumsum(co2_mt, axis=1).ravel()
    global_by_year = co2_mt.sum(axis=0)
    share = (co2_mt / global_by_year[None, :] * 100).ravel()
    out["fact_emissions_co2"] = pd.DataFrame(dict(
        country_id=cid_rep, year=yr_rep, co2_mt=co2_flat,
        co2_per_capita_t=co2_flat * 1e6 / pop_flat,
        co2_per_gdp_kg=co2_flat * 1e9 / gdp_flat,
        coal_co2_mt=coal, oil_co2_mt=oil, gas_co2_mt=gas, cement_co2_mt=cement,
        cumulative_co2_mt=cum, share_global_co2=share.astype("float32"), source_id=1))
    # GCB variant (source_id 8) for cross-source reconciliation (~3% difference)
    gcb = out["fact_emissions_co2"].copy()
    gcb["co2_mt"] = gcb["co2_mt"] * (1 + rng.normal(0, 0.03, len(gcb)))
    gcb["source_id"] = 8
    out["fact_emissions_co2"] = pd.concat([out["fact_emissions_co2"], gcb], ignore_index=True)

    # --- fact_ghg_emissions (GHG = CO2 * factor + CH4 + N2O)
    ch4 = co2_flat * rng.uniform(0.10, 0.30, co2_flat.size)
    n2o = co2_flat * rng.uniform(0.03, 0.10, co2_flat.size)
    ghg = co2_flat + ch4 + n2o
    out["fact_ghg_emissions"] = pd.DataFrame(dict(
        country_id=cid_rep, year=yr_rep, ghg_total_mt_co2e=ghg,
        ch4_mt_co2e=ch4, n2o_mt_co2e=n2o, ghg_per_capita_t=ghg * 1e6 / pop_flat, source_id=6))

    # --- fact_emissions_by_sector (6 sectors, CO2)
    weights = np.array([0.38, 0.22, 0.20, 0.10, 0.05, 0.05])      # Energy..Buildings
    sec_rows = []
    for s_idx, w in enumerate(weights, start=1):
        em = co2_flat * w * (1 + rng.normal(0, 0.05, co2_flat.size))
        sec_rows.append(pd.DataFrame(dict(country_id=cid_rep, year=yr_rep, sector_id=s_idx,
                                          gas="CO2", emissions_mt_co2e=np.clip(em, 0, None),
                                          source_id=6)))
    out["fact_emissions_by_sector"] = pd.concat(sec_rows, ignore_index=True)

    # --- fact_energy (primary energy correlated to co2, renewables rising over time)
    primary = co2_flat * rng.uniform(2.5, 4.0, co2_flat.size)     # TWh proxy
    ren = np.clip((8 + 30 * np.tile(t, n) + 25 * np.repeat(dev, ny)) *
                  (1 + rng.normal(0, 0.12, co2_flat.size)), 2, 92).astype("float32")
    nuc = np.clip(rng.normal(6, 4, co2_flat.size) * np.repeat(dev, ny), 0, 35).astype("float32")
    low_carbon = np.clip(ren + nuc, 0, 98).astype("float32")
    fossil = np.clip(100 - low_carbon, 2, 98).astype("float32")
    out["fact_energy"] = pd.DataFrame(dict(
        country_id=cid_rep, year=yr_rep, primary_energy_twh=primary,
        fossil_share_pct=fossil, renewables_share_pct=ren, nuclear_share_pct=nuc,
        low_carbon_share_pct=low_carbon,
        electricity_demand_twh=primary * rng.uniform(0.35, 0.55, co2_flat.size),
        energy_per_capita_kwh=primary * 1e9 / pop_flat, source_id=2))

    # --- fact_socioeconomic (tall: 25 indicators)
    soc = []
    # id1 GDP, id2 population, id3 gdp_pc, id7 co2 per capita reuse computed values
    soc.append(pd.DataFrame(dict(country_id=cid_rep, indicator_id=1, year=yr_rep,
                                 value=gdp_flat, source_id=3)))
    soc.append(pd.DataFrame(dict(country_id=cid_rep, indicator_id=2, year=yr_rep,
                                 value=pop_flat, source_id=3)))
    soc.append(pd.DataFrame(dict(country_id=cid_rep, indicator_id=3, year=yr_rep,
                                 value=gdp_pc.ravel(), source_id=3)))
    soc.append(pd.DataFrame(dict(country_id=cid_rep, indicator_id=7, year=yr_rep,
                                 value=co2_flat * 1e6 / pop_flat, source_id=3)))
    soc.append(pd.DataFrame(dict(country_id=cid_rep, indicator_id=23, year=yr_rep,
                                 value=ren.astype("float64"), source_id=3)))
    # remaining indicators: plausible ranges with mild dev/time dependence
    ranges = {4: (20, 88), 5: (45, 84), 6: (35, 100), 8: (1, 45), 9: (2, 28),
              10: (2, 8), 11: (1.2, 6.5), 12: (2, 450), 13: (5, 90), 14: (-2, 30),
              15: (2, 17), 16: (200, 8000), 17: (1, 70), 18: (1, 90), 19: (0, 96),
              20: (24, 63), 21: (10, 180), 22: (12, 80), 24: (1, 60), 25: (3, 1100)}
    dev_rep = np.repeat(dev, ny)
    t_rep = np.tile(t, n)
    for ind, (lo, hi) in ranges.items():
        base = lo + (hi - lo) * (0.3 + 0.6 * dev_rep)
        trend = (hi - lo) * 0.15 * t_rep * (1 if ind in (4, 5, 6, 19) else 0)
        val = np.clip(base + trend + rng.normal(0, (hi - lo) * 0.06, base.size), lo, hi)
        soc.append(pd.DataFrame(dict(country_id=cid_rep, indicator_id=ind, year=yr_rep,
                                     value=val, source_id=3)))
    out["fact_socioeconomic"] = pd.concat(soc, ignore_index=True)

    # --- fact_vulnerability (ND-GAIN, 1995-2024)
    vy = np.arange(1995, 2025)
    nvy = len(vy)
    vt = (vy - 1995) / (2024 - 1995)
    ndg = (28 + 45 * dev[:, None]) + 6 * vt[None, :] + rng.normal(0, 2.5, (n, nvy))
    ndg = np.clip(ndg, 20, 85)
    out["fact_vulnerability"] = pd.DataFrame(dict(
        country_id=np.repeat(cid, nvy), year=np.tile(vy, n),
        nd_gain_index=ndg.ravel().astype("float32"),
        vulnerability=np.clip(0.7 - 0.4 * np.repeat(dev, nvy) +
                              rng.normal(0, 0.05, n * nvy), 0.2, 0.8).astype("float32"),
        readiness=np.clip(0.25 + 0.5 * np.repeat(dev, nvy) +
                          rng.normal(0, 0.05, n * nvy), 0.1, 0.85).astype("float32"),
        source_id=4))

    # --- fact_disasters (sparse; frequency rises over decades, worse for low dev)
    dy = np.arange(1970, 2025)
    drows = []
    for j in range(n):
        base_rate = 0.20 + 0.6 * (1 - dev[j])
        for ti, y in enumerate(dy):
            climate_factor = 1 + 0.9 * (y - 1970) / 54
            for dt in range(1, 9):
                lam = base_rate * climate_factor * (0.6 if dt in (3, 4, 6) else 1.0) * 0.5
                ev = rng.poisson(lam)
                if ev > 0:
                    deaths = int(rng.gamma(1.5, 200 * (1 - dev[j]) + 5) * ev)
                    affected = int(deaths * rng.uniform(80, 600))
                    damage = float(rng.gamma(2.0, 50_000 * (0.3 + dev[j])) * ev)  # k USD
                    drows.append((cid[j], int(y), dt, int(ev), deaths, affected, damage))
    dd = pd.DataFrame(drows, columns=["country_id", "year", "disaster_type_id", "events",
                                      "total_deaths", "total_affected", "total_damage_usd_k"])
    dd["source_id"] = 5
    out["fact_disasters"] = dd

    # --- fact_agriculture (6 item/element combos)
    combos = [("Cereals", "Production", "tonnes"), ("Cereals", "Area harvested", "ha"),
              ("Forest land", "Area", "1000 ha"), ("Rice", "Production", "tonnes"),
              ("Livestock", "Stocks", "head"), ("Fertilizers", "Use", "tonnes")]
    agr = []
    for item, element, unit in combos:
        scale = {"Production": 5e5, "Area harvested": 2e5, "Area": 1e4,
                 "Stocks": 1e6, "Use": 1e5}[element]
        val = scale * (0.2 + np.repeat(dev, ny)) * (0.5 + np.tile(np.linspace(0.6, 1.6, ny), n))
        val *= (1 + rng.normal(0, 0.08, val.size))
        agr.append(pd.DataFrame(dict(country_id=cid_rep, year=yr_rep, item=item,
                                     element=element, value=np.clip(val, 0, None),
                                     unit=unit, source_id=7)))
    out["fact_agriculture"] = pd.concat(agr, ignore_index=True)

    # --- monthly: temperature (global + all countries), precipitation, co2, sea level
    months = pd.date_range(f"{MONTH_Y0}-01-01", "2024-12-01", freq="MS")
    nm = len(months)
    myear = months.year.to_numpy()
    mmon = months.month.to_numpy()
    gt = (myear - 1960) / (2024 - 1960)
    # global temperature anomaly trend
    g_anom = (-0.05 + 1.15 * gt) + 0.15 * np.sin(2 * np.pi * (mmon / 12)) + rng.normal(0, 0.08, nm)
    temp_rows = [pd.DataFrame(dict(country_id=0, date=months.date,
                                   temp_anomaly_c=g_anom.astype("float32"),
                                   temp_abs_c=(14.0 + g_anom).astype("float32"), source_id=10))]
    for j in range(n):
        seasonal_amp = 2 + 12 * abs(rng.normal(0, 1))             # higher latitudes vary more
        anom = (-0.1 + 1.3 * gt) + rng.normal(0, 0.25, nm) + 0.2 * np.sin(2 * np.pi * mmon / 12)
        base_temp = 27 - 0.35 * seasonal_amp
        absol = base_temp + seasonal_amp * np.sin(2 * np.pi * (mmon - 1) / 12) + anom
        temp_rows.append(pd.DataFrame(dict(country_id=cid[j], date=months.date,
                                           temp_anomaly_c=anom.astype("float32"),
                                           temp_abs_c=absol.astype("float32"), source_id=11)))
    out["fact_temperature"] = pd.concat(temp_rows, ignore_index=True)

    # precipitation: 1980-2024 monthly, all countries
    pmonths = pd.date_range("1980-01-01", "2024-12-01", freq="MS")
    pm = len(pmonths)
    pmon = pmonths.month.to_numpy()
    prec_rows = []
    for j in range(n):
        base = rng.uniform(20, 180)
        seas = base * (0.4 + 0.6 * np.sin(2 * np.pi * (pmon - rng.integers(1, 12)) / 12) ** 2)
        val = np.clip(seas * (1 + rng.normal(0, 0.25, pm)), 0, None)
        prec_rows.append(pd.DataFrame(dict(country_id=cid[j], date=pmonths.date,
                                           precip_mm=val.astype("float32"), source_id=14)))
    out["fact_precipitation"] = pd.concat(prec_rows, ignore_index=True)

    # atmospheric CO2 (Mauna Loa) monthly 1958-2024
    co2months = pd.date_range("1958-03-01", "2024-12-01", freq="MS")
    cm = len(co2months)
    cyr = (co2months.year + (co2months.month - 1) / 12).to_numpy()
    trend = 280 + 0.0 + (cyr - 1958) ** 1.18 * 0.55               # accelerating rise
    trend = 315 + (cyr - 1958) * 1.45 + ((cyr - 1958) ** 2) * 0.0125
    seasonal = 3.0 * np.sin(2 * np.pi * (co2months.month.to_numpy() - 4) / 12)
    ppm = trend + seasonal + rng.normal(0, 0.3, cm)
    out["fact_co2_atmospheric"] = pd.DataFrame(dict(
        date=co2months.date, station="Mauna Loa", co2_ppm=ppm.astype("float32"),
        co2_trend_ppm=trend.astype("float32"), source_id=9))

    # sea level monthly 1880-2024
    smonths = pd.date_range("1900-01-01", "2024-12-01", freq="MS")
    sm = len(smonths)
    syr = (smonths.year + (smonths.month - 1) / 12).to_numpy()
    gmsl = -150 + (syr - 1880) * 1.7 + ((syr - 1990).clip(0) ** 2) * 0.02 + rng.normal(0, 4, sm)
    out["fact_sea_level"] = pd.DataFrame(dict(
        date=smonths.date, gmsl_mm=gmsl.astype("float32"),
        gmsl_uncertainty_mm=rng.uniform(2, 8, sm).astype("float32"), source_id=15))

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", action="store_true", help="print row counts only (no write)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    countries = build_countries()
    dims = {
        "dim_country": countries,
        "dim_date": build_dim_date(),
        "dim_indicator": build_indicators(),
        "dim_disaster_type": build_disaster_types(),
        "dim_sector": build_sectors(),
        "dim_source": build_sources(),
    }
    facts = build_facts(countries)

    all_tables = {**dims, **facts}
    fact_rows = 0
    print(f"{'table':32} {'rows':>12}")
    print("-" * 46)
    for name, df in all_tables.items():
        print(f"{name:32} {len(df):>12,}")
        if name.startswith("fact_"):
            fact_rows += len(df)
        if not args.rows:
            df.to_parquet(os.path.join(OUT_DIR, f"{name}.parquet"), index=False)
    print("-" * 46)
    print(f"{'TOTAL fact rows':32} {fact_rows:>12,}")
    print(f"{'countries':32} {len(countries):>12,}")
    if not args.rows:
        print(f"\nParquet written to {OUT_DIR}")


if __name__ == "__main__":
    main()
