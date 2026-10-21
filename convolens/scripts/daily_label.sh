#!/usr/bin/env bash
# One capped day of Gemini free-tier labelling. Safe to run repeatedly: labelled conversations are cached by content
# hash and skipped, so each run only spends requests on new work, and it stops at MAX_REQUESTS.
#
#   DATASET_ID=ds_xxx MAX_REQUESTS=12 scripts/daily_label.sh
#
# LABELS (default data/labels/gemini_labels.jsonl) carries progress between machines: it is imported first and
# re-exported at the end. Activation happens automatically once every conversation in the dataset has a label.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
: "${DATASET_ID:?set DATASET_ID}"
LABELS="${LABELS:-$here/data/labels/gemini_labels.jsonl}"
mkdir -p "$(dirname "$LABELS")"
cd "$here/backend"
if [ -f "$LABELS" ]; then uv run python -m app.ingestion.cli import-labels "$DATASET_ID" "$LABELS"; fi
MODEL_PROVIDER=gemini GEMINI_KEY_VIA_PROXY="${GEMINI_KEY_VIA_PROXY:-true}" GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash-lite}" \
  MODEL_MAX_RETRIES=0 uv run python -m app.ingestion.cli analyze "$DATASET_ID" --max-requests "${MAX_REQUESTS:-12}"
uv run python -m app.ingestion.cli export-labels "$LABELS"
