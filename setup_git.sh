set -e

REMOTE_URL="https://github.com/MakoMuseridze/climate_dw.git"
GIT_NAME="Mako Museridze"
GIT_EMAIL="m_museridze@cu.edu.ge"

cd "$(dirname "$0")"
if [ ! -f README.md ] || [ ! -d etl ]; then
  echo "ERROR: run this from the climate_dw project root (where README.md and etl/ live)." >&2
  exit 1
fi

# Start from a clean slate (safe: nothing is pushed yet).
rm -rf .git
git init -b main
git config user.name  "$GIT_NAME"
git config user.email "$GIT_EMAIL"

commit () { msg="$1"; shift; git add "$@"; git commit -m "$msg"; }

commit "Project scaffolding: Docker stack (ClickHouse 24.8 + Grafana 11), Makefile, dependencies" \
  .gitignore Makefile requirements.txt docker-compose.yml docker/ data/raw/.gitkeep data/staging/.gitkeep

commit "ClickHouse star schema: 6 dimensions, 12 fact tables, materialized views, dictionaries, lineage/audit" \
  sql/ddl/

commit "ETL pipeline: source registry, per-source extractors, orchestrator, dimension seeding" \
  etl/__init__.py etl/config.py etl/db.py etl/countries.py etl/dimensions.py \
  etl/seed_dimensions.py etl/sources.py etl/run_etl.py etl/real/

commit "Analytical query library (12 cross-domain queries) + dictionary-accelerated examples" \
  sql/queries/

commit "Data-quality suite (11 checks -> audit log) and offline self-test fixture" \
  etl/dq.py etl/synthetic/ scripts/

commit "Grafana dashboards: provisioned ClickHouse datasource + overview (9 panels, 6 themes)" \
  dashboards/

commit "Documentation: architecture, data dictionary, installation, query reference, user guide, README, MIT license" \
  docs/ README.md CONTRIBUTING.md LICENSE

# Safety net: commit anything not captured above (should be nothing).
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "Add remaining project files"
fi

echo
echo "Local history:"
git log --oneline

echo
echo "Pushing to $REMOTE_URL ..."
git remote add origin "$REMOTE_URL"
git push -u origin main

echo
echo "Done. Verify at: ${REMOTE_URL%.git}"