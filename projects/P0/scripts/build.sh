#!/usr/bin/env bash
# Build the hmda_dw star schema from hmda_staging: runs sql/build/*.sql in
# filename order with the bq CLI. Every step uses CREATE OR REPLACE, so it is
# safe to rerun. Stops at the first failing step, including a failed check in
# 08_checks.sql.
#
#   ./scripts/build.sh
#
# Needs the gcloud SDK (for bq) and GCP_PROJECT in .env or the environment.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi
: "${GCP_PROJECT:?set GCP_PROJECT in .env}"
command -v bq >/dev/null || { echo "bq not found: install the Google Cloud SDK" >&2; exit 1; }

for file in sql/build/*.sql; do
  echo "== $file"
  # the last step prints the table row counts; the others print nothing
  format=none
  [[ "$file" == *checks.sql ]] && format=pretty
  bq --project_id="$GCP_PROJECT" --location=US query \
     --use_legacy_sql=false --quiet --format="$format" < "$file"
done
echo "hmda_dw built in $GCP_PROJECT"
