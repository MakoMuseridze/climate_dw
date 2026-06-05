"""Central configuration: ClickHouse connection + filesystem paths.

Connection settings come from environment variables (override the defaults,
which match the bundled docker-compose). Copy nothing secret into git.
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW = os.path.join(REPO, "data", "raw")        # cached source downloads
DATA_STAGING = os.path.join(REPO, "data", "staging")  # intermediate parquet
SQL_DDL = os.path.join(REPO, "sql", "ddl")

DATABASE = os.getenv("CH_DB", "climate")

CLICKHOUSE = dict(
    host=os.getenv("CH_HOST", "localhost"),
    port=int(os.getenv("CH_PORT", "8123")),          # HTTP interface
    username=os.getenv("CH_USER", "default"),
    password=os.getenv("CH_PASS", "climate"),
)

# DDL files, applied in order, to stand up an empty warehouse.
DDL_FILES = [
    "00_database.sql",
    "01_dimensions.sql",
    "02_facts.sql",
    "03_materialized_views.sql",
    "05_lineage_audit.sql",
    "04_dictionaries.sql",   # last: dictionaries read from the (now-existing) dims
]

os.makedirs(DATA_RAW, exist_ok=True)
os.makedirs(DATA_STAGING, exist_ok=True)
