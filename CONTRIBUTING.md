# Contributing

This is an academic project (Caucasus University — Bachelor's Project), but the
codebase is structured so that new data sources and checks can be added cleanly.
These guidelines document the conventions used throughout.

## Development setup

```bash
git clone https://github.com/MakoMuseridze/climate_dw.git
cd climate_dw
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make install
```

Run the offline self-test before and after any change — it needs no Docker,
server, or downloads:

```bash
pip install chdb        # Linux/macOS; one-time, for the self-test only
make validate
```

A change is "green" when `make validate` reports `RESULT: PASS` (all queries
< 2 s, data-quality pass rate ≥ 95%, ≥ 500k fixture rows).

## Project conventions

- **Python 3.11+**, PEP 8, 4-space indent. Keep modules small and single-purpose.
- **One extractor per source** in `etl/real/`, each subclassing `BaseExtractor`
  (`etl/real/base.py`). An extractor only knows how to *extract → parse →
  harmonize*; loading, lineage logging, and country resolution are handled by the
  base class and the orchestrator.
- **`etl/sources.py` is the single source of truth** for source IDs, URLs,
  licenses, and coverage. `source_id` values are stable foreign keys — never
  renumber an existing source.
- **SQL lives in `sql/`**, not in Python string literals. DDL is split by concern
  (`00_database` → `05_lineage_audit`) and applied in filename order.
- **Country harmonization** always goes through `etl/countries.py`
  (`CountryResolver`) so every fact resolves to the same `country_id`.

## Adding a new data source

1. Add an entry to `SOURCES` in `etl/sources.py` (next free `source_id`).
2. Create `etl/real/<source>.py` with a class subclassing `BaseExtractor`,
   setting `source_id`, `source_name`, `target_table`, and implementing the
   parse/harmonize step that returns a DataFrame matching the target table's
   columns.
3. Register it in the `REGISTRY` (and a `GROUPS` bucket) in `etl/run_etl.py`.
4. If it needs a new table, add the DDL to `sql/ddl/02_facts.sql` and document
   the columns in `docs/data_dictionary.md`.
5. Run `python -m etl.run_etl --sources <source> --dry-run` to preview, then
   load for real and re-run `make dq`.

## Commit style

- Small, logical commits with imperative subject lines
  (e.g. `Add GPCC precipitation extractor`).
- Group related schema + ETL + docs changes together where it tells a clearer story.
- Do not commit anything under `data/raw/` or `data/staging/` (already in
  `.gitignore`), credentials (`.cdsapirc`, `secrets.yml`), or generated caches.

## Reporting issues

Open a GitHub issue describing the source/query involved, the command run, and
the full console output (set `ETL_DEBUG=1` for a traceback on a failed load).
