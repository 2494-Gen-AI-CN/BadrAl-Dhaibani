#!/usr/bin/env bash
# Download the raw HMDA files (LAR CSV + filers JSON per state x year),
# the Census county FIPS reference and the county shapes (for the map) into data/raw/.
# Re-running skips files that already exist; pass --force to re-download.
set -euo pipefail

STATES=(OH NC)
YEARS=(2023 2024 2025)
API="https://ffiec.cfpb.gov/v2/data-browser-api/view"
COUNTY_URL="https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"
SHAPES_URL="https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_20m.zip"  # county shapes for the map

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/data/raw"
FORCE="${1:-}"
mkdir -p "$RAW"

fetch() {  # fetch <url> <dest>
  local url="$1" dest="$2"
  if [[ -s "$dest" && "$FORCE" != "--force" ]]; then
    echo "skip  $(basename "$dest") (exists)"
    return
  fi
  echo "get   $(basename "$dest")"
  curl -fsSL --compressed --retry 3 --retry-delay 5 -o "$dest.part" "$url"
  mv "$dest.part" "$dest"
}

for state in "${STATES[@]}"; do
  for year in "${YEARS[@]}"; do
    fetch "$API/csv?states=$state&years=$year"     "$RAW/lar_${state}_${year}.csv"
    fetch "$API/filers?states=$state&years=$year"  "$RAW/filers_${state}_${year}.json"
  done
done

fetch "$COUNTY_URL" "$RAW/counties_2020.txt"
fetch "$SHAPES_URL" "$RAW/cb_2023_us_county_20m.zip"

echo "done: $(ls "$RAW" | wc -l) files in data/raw/"
