#!/usr/bin/env bash
# Ingest all scraped builds into the TeachMeWoW database.
# Usage: ./ingest.sh [--api-url URL]
#
# Reads manifest.json, finds specs with status "scraped",
# POSTs their YAML to the ingestion endpoint, and updates
# the manifest to "ingested" or "error".

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="$SCRIPT_DIR/manifest.json"
BUILDS_DIR="$SCRIPT_DIR/builds"
API_URL="${1:-http://localhost:8000}"

if ! command -v jq &> /dev/null; then
  echo "Error: jq is required. Install with: brew install jq"
  exit 1
fi

if [ ! -f "$MANIFEST" ]; then
  echo "Error: manifest.json not found at $MANIFEST"
  exit 1
fi

# Get all unique classes that have at least one "scraped" spec
CLASSES=$(jq -r '.specs[] | select(.status == "scraped") | .class' "$MANIFEST" | sort -u)

if [ -z "$CLASSES" ]; then
  echo "No specs with status 'scraped' found in manifest. Nothing to ingest."
  echo "Run the scrape-builds skill first to populate builds."
  exit 0
fi

TOTAL=0
SUCCESS=0
ERRORS=0

for CLASS in $CLASSES; do
  YAML_FILE="$BUILDS_DIR/$CLASS.yaml"

  if [ ! -f "$YAML_FILE" ]; then
    echo "WARNING: $YAML_FILE not found but manifest has scraped specs for $CLASS. Skipping."
    continue
  fi

  echo "Ingesting $CLASS..."
  TOTAL=$((TOTAL + 1))

  HTTP_CODE=$(curl -s -o /tmp/ingest_response.json -w "%{http_code}" \
    -X POST "$API_URL/builds/ingest/yaml" \
    -H "Content-Type: text/yaml" \
    --data-binary "@$YAML_FILE")

  if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "  OK ($HTTP_CODE) — $(cat /tmp/ingest_response.json)"
    SUCCESS=$((SUCCESS + 1))

    # Update all specs of this class from "scraped" to "ingested"
    UPDATED=$(jq --arg cls "$CLASS" '
      .specs |= map(
        if .class == $cls and .status == "scraped"
        then .status = "ingested"
        else . end
      ) | .last_updated = (now | todate)
    ' "$MANIFEST")
    echo "$UPDATED" > "$MANIFEST"
  else
    echo "  FAILED ($HTTP_CODE) — $(cat /tmp/ingest_response.json)"
    ERRORS=$((ERRORS + 1))

    # Update all specs of this class from "scraped" to "error"
    UPDATED=$(jq --arg cls "$CLASS" --arg err "HTTP $HTTP_CODE" '
      .specs |= map(
        if .class == $cls and .status == "scraped"
        then .status = "error" | .error_message = $err
        else . end
      ) | .last_updated = (now | todate)
    ' "$MANIFEST")
    echo "$UPDATED" > "$MANIFEST"
  fi
done

echo ""
echo "Done. $SUCCESS/$TOTAL classes ingested successfully. $ERRORS errors."
rm -f /tmp/ingest_response.json
