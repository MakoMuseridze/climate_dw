"""Canonical dimension / reference data for the REAL pipeline.

These are genuine reference values (real ISO3 codes, real WDI indicator codes,
EM-DAT disaster hierarchy, EDGAR sectors, the source registry). They are loaded
by `etl.seed_dimensions` before any fact ETL runs, because fact rows resolve
country_id / indicator_id / source_id against them.

INDICATORS is the contract between the World Bank WDI extractor and
fact_socioeconomic: indicator_id <-> WDI indicator code.
"""
from __future__ import annotations
import pandas as pd

from .sources import SOURCES

# ----- income classification (World Bank groups, ISO3). Default Lower-middle.
_HIGH = set("USA CAN GBR FRA DEU ITA ESP NLD BEL AUT CHE SWE NOR DNK FIN IRL ISL LUX "
            "PRT GRC JPN KOR AUS NZL SGP ISR ARE QAT KWT BHR OMN SAU BRN HKG TWN CYP MLT "
            "SVN CZE EST LVA LTU SVK POL HRV HUN CHL URY PAN".split())
_UPPER = set("CHN RUS BRA MEX TUR ARG ZAF MYS THA KAZ COL PER ROU BGR SRB BLR GEO ARM AZE "
             "MKD MNE BIH ALB CRI DOM ECU PRY JAM BWA GAB NAM MUS LBN IRQ IRN JOR DZA "
             "CUB GTM".split())
_LOW = set("AFG ETH COD MLI NER TCD SOM SSD UGA RWA MWI MOZ BFA BDI GIN GNB LBR SLE TGO "
           "MDG CAF YEM SDN ERI GMB COG".split())


def income_group(iso3: str) -> str:
    if iso3 in _HIGH:
        return "High income"
    if iso3 in _UPPER:
        return "Upper-middle income"
    if iso3 in _LOW:
        return "Low income"
    return "Lower-middle income"


# 25 World Bank WDI indicators pulled by the WDI extractor.
# (indicator_id, WDI code, name, unit, theme)
INDICATORS = [
    (1,  "NY.GDP.MKTP.CD",     "GDP (current US$)",                  "USD",          "Economy"),
    (2,  "SP.POP.TOTL",        "Population, total",                  "persons",      "Demographics"),
    (3,  "NY.GDP.PCAP.CD",     "GDP per capita (current US$)",       "USD",          "Economy"),
    (4,  "SP.URB.TOTL.IN.ZS",  "Urban population (% of total)",      "%",            "Demographics"),
    (5,  "SP.DYN.LE00.IN",     "Life expectancy at birth",           "years",        "Health"),
    (6,  "EG.ELC.ACCS.ZS",     "Access to electricity (% pop)",      "%",            "Energy"),
    (7,  "EN.GHG.CO2.PC.CE.AR5", "CO2 emissions per capita",         "t",            "Environment"),
    (8,  "NV.AGR.TOTL.ZS",     "Agriculture value added (% GDP)",    "%",            "Economy"),
    (9,  "SL.UEM.TOTL.ZS",     "Unemployment (% labor force)",       "%",            "Economy"),
    (10, "SE.XPD.TOTL.GD.ZS",  "Govt education expenditure (% GDP)", "%",            "Education"),
    (11, "SP.DYN.TFRT.IN",     "Fertility rate, total",              "births/woman", "Demographics"),
    (12, "EN.POP.DNST",        "Population density",                 "people/km2",   "Demographics"),
    (13, "NE.EXP.GNFS.ZS",     "Exports of goods/services (% GDP)",  "%",            "Economy"),
    (14, "FP.CPI.TOTL.ZG",     "Inflation, consumer prices",         "%",            "Economy"),
    (15, "SH.XPD.CHEX.GD.ZS",  "Health expenditure (% GDP)",         "%",            "Health"),
    (16, "EG.USE.PCAP.KG.OE",  "Energy use per capita",              "kg oil eq",    "Energy"),
    (17, "AG.LND.FRST.ZS",     "Forest area (% land)",               "%",            "Environment"),
    (18, "ER.H2O.FWTL.ZS",     "Freshwater withdrawal (% resources)", "%",           "Environment"),
    (19, "IT.NET.USER.ZS",     "Individuals using internet (%)",     "%",            "Technology"),
    (20, "SI.POV.GINI",        "Gini index",                         "index",        "Inequality"),
    (21, "GC.DOD.TOTL.GD.ZS",  "Govt debt (% GDP)",                  "%",            "Economy"),
    (22, "SP.RUR.TOTL.ZS",     "Rural population (% of total)",      "%",            "Demographics"),
    (23, "EG.FEC.RNEW.ZS",     "Renewable energy consumption (%)",   "%",            "Energy"),
    (24, "AG.LND.ARBL.ZS",     "Arable land (% land)",               "%",            "Agriculture"),
    (25, "SH.STA.MMRT",        "Maternal mortality ratio",           "per 100k",     "Health"),
]
INDICATOR_CODE_TO_ID = {code: iid for (iid, code, *_rest) in INDICATORS}

# EM-DAT disaster hierarchy. EM-DAT "Disaster Type" -> id.
DISASTER_TYPES = [
    (1, "Natural", "Hydrological",   "Flood",               "Riverine flood"),
    (2, "Natural", "Meteorological", "Storm",               "Tropical cyclone"),
    (3, "Natural", "Climatological", "Drought",             ""),
    (4, "Natural", "Climatological", "Wildfire",            "Forest fire"),
    (5, "Natural", "Geophysical",    "Earthquake",          "Ground movement"),
    (6, "Natural", "Meteorological", "Extreme temperature", "Heat wave"),
    (7, "Natural", "Hydrological",   "Mass movement (wet)", "Landslide"),
    (8, "Natural", "Biological",     "Epidemic",            "Viral disease"),
    (9, "Natural", "Geophysical",    "Volcanic activity",   ""),
    (10, "Natural", "Climatological", "Glacial lake outburst", ""),
]
DISASTER_TYPE_TO_ID = {t[3]: t[0] for t in DISASTER_TYPES}

# EDGAR / IPCC sectors.
SECTORS = [
    (1, "Energy", "1A"), (2, "Industry", "2"), (3, "Transport", "1A3"),
    (4, "Agriculture", "3"), (5, "Waste", "4"), (6, "Buildings", "1A4"),
    (7, "Other", "5"),
]


def build_country_dim() -> pd.DataFrame:
    """Real country dimension from country_converter (genuine ISO3/region)."""
    import country_converter as coco
    data = coco.CountryConverter().data
    cols = data[["ISO3", "ISO2", "name_short", "continent", "UNregion"]].copy()
    cols = cols[cols["ISO3"].str.match(r"^[A-Z]{3}$", na=False)]
    cols = cols[~cols["name_short"].str.contains(
        "Antarctica|Bouvet|Heard|Minor|Svalbard|Pitcairn|Tokelau|Niue|Wallis|"
        "French Southern|British Indian|Norfolk|Cocos|Christmas|Vatican|"
        "Saint Helena|Aland Is|Åland", case=False, na=False)]
    cols = cols.drop_duplicates("ISO3").reset_index(drop=True)
    rows = [dict(country_id=0, iso3="WLD", iso2="WD", country_name="World",
                 region="World", subregion="World", continent="World",
                 income_group="Aggregate", un_member=0, area_km2=148940000.0,
                 valid_from="1900-01-01", valid_to="2200-01-01", is_current=1)]
    for i, r in enumerate(cols.itertuples(index=False), start=1):
        rows.append(dict(
            country_id=i, iso3=r.ISO3,
            iso2=(r.ISO2 if isinstance(r.ISO2, str) and len(r.ISO2) == 2 else "XX"),
            country_name=str(r.name_short), region=str(r.continent),
            subregion=str(r.UNregion), continent=str(r.continent),
            income_group=income_group(r.ISO3), un_member=1, area_km2=0.0,
            valid_from="1900-01-01", valid_to="2200-01-01", is_current=1))
    return pd.DataFrame(rows)


def build_indicator_dim() -> pd.DataFrame:
    return pd.DataFrame([dict(indicator_id=i, indicator_code=c, indicator_name=n,
                              unit=u, theme=t, source="World Bank WDI")
                         for (i, c, n, u, t) in INDICATORS])


def build_disaster_dim() -> pd.DataFrame:
    return pd.DataFrame([dict(disaster_type_id=i, disaster_group=g, disaster_subgroup=sg,
                              disaster_type=t, disaster_subtype=st)
                         for (i, g, sg, t, st) in DISASTER_TYPES])


def build_sector_dim() -> pd.DataFrame:
    return pd.DataFrame([dict(sector_id=i, sector_name=n, ipcc_code=c)
                         for (i, n, c) in SECTORS])


def build_source_dim() -> pd.DataFrame:
    return pd.DataFrame([dict(source_id=s["source_id"], source_name=s["source_name"],
                              domain=s["domain"], format=s["format"], url=s["url"],
                              license=s["license"], coverage=s["coverage"]) for s in SOURCES])


def build_date_dim() -> pd.DataFrame:
    d = pd.date_range("1900-01-01", "2024-12-31", freq="D")
    return pd.DataFrame(dict(
        date=d.date, year=d.year.astype("uint16"), month=d.month.astype("uint8"),
        day=d.day.astype("uint8"), quarter=d.quarter.astype("uint8"),
        decade=((d.year // 10) * 10).astype("uint16"),
        day_of_year=d.dayofyear.astype("uint16"), month_name=d.strftime("%B"),
        is_year_start=((d.month == 1) & (d.day == 1)).astype("uint8"),
        is_month_start=(d.day == 1).astype("uint8")))
