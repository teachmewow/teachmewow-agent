#!/usr/bin/env bash
# Ingest all scraped builds into the TeachMeWoW database.
# Usage: ./ingest.sh [--api-url URL]
#
# Reads manifest.json, finds specs with status "scraped",
# POSTs their YAML to the ingestion endpoint, and updates
# the manifest based on the response:
#   - All builds OK        → status = "ingested"
#   - Some builds failed   → status = "scraped" (needs re-ingestion)
#   - HTTP error           → status = "error"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="$SCRIPT_DIR/manifest.json"
BUILDS_DIR="$SCRIPT_DIR/builds"
API_URL="${1:-http://localhost:8000}"
RESP_FILE=$(mktemp)

cleanup() { rm -f "$RESP_FILE"; }
trap cleanup EXIT

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
CLEAN=0
PARTIAL=0
FAILED=0

for CLASS in $CLASSES; do
  YAML_FILE="$BUILDS_DIR/$CLASS.yaml"

  if [ ! -f "$YAML_FILE" ]; then
    echo "WARNING: $YAML_FILE not found but manifest has scraped specs for $CLASS. Skipping."
    continue
  fi

  TOTAL=$((TOTAL + 1))

  HTTP_CODE=$(curl -s -o "$RESP_FILE" -w "%{http_code}" \
    -X POST "$API_URL/builds/ingest/yaml" \
    -H "Content-Type: text/yaml" \
    --data-binary "@$YAML_FILE")

  if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    INGESTED=$(jq -r '.ingested // 0' "$RESP_FILE")
    SPECS_PROC=$(jq -r '.specs_processed // 0' "$RESP_FILE")
    ERROR_COUNT=$(jq -r '.errors | length' "$RESP_FILE")

    if [ "$ERROR_COUNT" -eq 0 ]; then
      # Clean success — all builds ingested
      echo "  ✓ $CLASS — $INGESTED builds ingested ($SPECS_PROC specs)"
      CLEAN=$((CLEAN + 1))

      # Mark all scraped specs of this class as "ingested"
      UPDATED=$(jq --arg cls "$CLASS" '
        .specs |= map(
          if .class == $cls and .status == "scraped"
          then .status = "ingested" | del(.error_message)
          else . end
        ) | .last_updated = (now | todate)
      ' "$MANIFEST")
      echo "$UPDATED" > "$MANIFEST"
    else
      # Partial success — some builds failed normalization
      PARTIAL=$((PARTIAL + 1))
      echo "  ⚠ $CLASS — $INGESTED builds ingested, $ERROR_COUNT failed:"
      jq -r '.errors[]' "$RESP_FILE" | while IFS= read -r err; do
        echo "      $err"
      done

      # Keep status as "scraped" so re-ingestion picks them up
      echo "    → Kept as 'scraped' for re-ingestion"
    fi
  else
    # HTTP-level failure
    FAILED=$((FAILED + 1))
    echo "  ✗ $CLASS — HTTP $HTTP_CODE"
    cat "$RESP_FILE" 2>/dev/null | head -3

    # Mark as error
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
echo "Done. $TOTAL classes processed:"
[ "$CLEAN"   -gt 0 ] && echo "  $CLEAN fully ingested"
[ "$PARTIAL" -gt 0 ] && echo "  $PARTIAL partially ingested (re-run to retry failed builds)"
[ "$FAILED"  -gt 0 ] && echo "  $FAILED failed (check API)"
