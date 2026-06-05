"""
Canonical data-source registry (single source of truth).

Used by:
  * the dim_source seed (provenance dimension)
  * the real-data ETL extractors (download URLs)
  * the load-lineage log (source_id / source_name / url / access_date)

`source_id` values are STABLE - fact tables store them as foreign keys.
URLs current as of June 2026; verify before a fresh download run
(several sources revise their hosting paths periodically).
"""

SOURCES = [
    # id, name, domain, format, url, coverage, license
    dict(source_id=1,  source_name="OWID CO2 Data",          domain="Emissions",     format="CSV",
         url="https://owid-public.owid.io/data/co2/owid-co2-data.csv",
         coverage="Global, 1750-2024", license="CC-BY 4.0"),  # mirror: raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv
    dict(source_id=2,  source_name="OWID Energy Data",       domain="Energy",        format="CSV",
         url="https://owid-public.owid.io/data/energy/owid-energy-data.csv",
         coverage="Global, 1900-2024", license="CC-BY 4.0"),  # mirror: raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv
    dict(source_id=3,  source_name="World Bank WDI",         domain="Socioeconomic", format="CSV/API",
         url="https://databank.worldbank.org/data/download/WDI_CSV.zip",
         coverage="200+ countries, 1960-2024", license="CC-BY 4.0"),
    dict(source_id=4,  source_name="ND-GAIN Index",          domain="Vulnerability", format="CSV",
         url="https://gain.nd.edu/our-work/country-index/download-data/",
         coverage="185+ countries, 1995-2023", license="CC-BY-NC-SA"),
    dict(source_id=5,  source_name="EM-DAT",                 domain="Disasters",     format="Excel",
         url="https://public.emdat.be/",
         coverage="Global, 1900-present", license="Free (registration)"),
    dict(source_id=6,  source_name="EDGAR v8.0",             domain="Emissions",     format="CSV/Excel",
         url="https://edgar.jrc.ec.europa.eu/dataset_ghg80",
         coverage="Global, 1970-2022", license="Free"),
    dict(source_id=7,  source_name="FAOSTAT",                domain="Agriculture",   format="CSV",
         url="https://bulks-faostat.fao.org/production/",
         coverage="245+ countries, 1961-2024", license="CC-BY 4.0"),
    dict(source_id=8,  source_name="Global Carbon Budget",   domain="Carbon Cycle",  format="Excel",
         url="https://globalcarbonbudgetdata.org/",
         coverage="Global, 1959-present", license="CC-BY 4.0"),
    dict(source_id=9,  source_name="NOAA GML CO2",           domain="Atmosphere",    format="TXT",
         url="https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt",
         coverage="Mauna Loa, 1958-present", license="Public domain"),
    dict(source_id=10, source_name="NASA GISTEMP v4",        domain="Temperature",   format="CSV",
         url="https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv",
         coverage="Global, 1880-present", license="Public domain"),
    dict(source_id=11, source_name="NOAAGlobalTemp",         domain="Temperature",   format="NetCDF",
         url="https://www.ncei.noaa.gov/data/noaa-global-surface-temperature/",
         coverage="Global grid, 1850-present", license="Public domain"),
    dict(source_id=12, source_name="HadCRUT5",               domain="Temperature",   format="NetCDF",
         url="https://www.metoffice.gov.uk/hadobs/hadcrut5/data/current/download.html",
         coverage="Global grid, 1850-present", license="Open Government"),
    dict(source_id=13, source_name="ERA5 Reanalysis",        domain="Multi-variable", format="NetCDF",
         url="https://cds.climate.copernicus.eu/",
         coverage="Global grid, 1940-present", license="Copernicus (free, registration)"),
    dict(source_id=14, source_name="GPCC",                   domain="Precipitation", format="NetCDF",
         url="https://opendata.dwd.de/climate_environment/GPCC/",
         coverage="Global land, 1891-present", license="Free"),
    dict(source_id=15, source_name="CSIRO Sea Level",        domain="Sea Level",     format="ASCII",
         url="https://www.cmar.csiro.au/sealevel/sl_data_cmar.html",
         coverage="Global, 1880-present", license="CC-BY 4.0"),
    dict(source_id=16, source_name="Climate TRACE",          domain="Emissions",     format="CSV",
         url="https://climatetrace.org/data",
         coverage="2.7M sources, 2015-2024", license="CC-BY 4.0"),
    dict(source_id=17, source_name="Global Forest Watch",    domain="Land Use",      format="CSV/GeoTIFF",
         url="https://www.globalforestwatch.org/",
         coverage="Global, 2000-2024", license="CC-BY 4.0"),
    dict(source_id=18, source_name="CHIRPS",                 domain="Precipitation", format="GeoTIFF",
         url="https://www.chc.ucsb.edu/data/chirps",
         coverage="50S-50N, 1981-present", license="Public domain"),
    # TEST FIXTURE ONLY - consumed by scripts/validate_local.py (offline self-test).
    # NOT loaded by the real ETL pipeline; no production fact rows reference this id.
    dict(source_id=99, source_name="SYNTHETIC (test fixture)", domain="All",          format="generated",
         url="local://etl/synthetic/generate.py",
         coverage="Offline self-test fixture only", license="N/A"),
]

SOURCE_BY_ID = {s["source_id"]: s for s in SOURCES}


def get(source_id: int) -> dict:
    return SOURCE_BY_ID[source_id]
