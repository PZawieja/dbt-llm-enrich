#!/usr/bin/env bash
# Rebuilds the committed demo from scratch with real API calls: three runs that
# show the cache at work. Needs ANTHROPIC_API_KEY; costs a few cents.
set -euo pipefail
export PYTHONUNBUFFERED=1
exec > >(tee live_demo.log) 2>&1
cd "$(dirname "$0")/.."
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "ANTHROPIC_API_KEY is not set in this shell; nothing was changed." >&2
    exit 1
fi
dbt_build() { (cd warehouse/dbt && uv run dbt build --profiles-dir . --exclude test_name:min_accuracy -q); }

: > enrichment/classifications.jsonl
: > enrichment/runs.jsonl

echo "== 1. prompt v1 on the tickets as they first arrived"
uv run python warehouse/generate.py --before-edits
dbt_build
uv run enrich run --prompt v1 --require-complete

echo "== 2. 20 customers add an update: only their tickets are sent"
uv run python warehouse/generate.py --golden-candidates warehouse/dbt/seeds/golden_ticket_labels.csv
dbt_build
uv run enrich plan --prompt v1
uv run enrich run --prompt v1 --require-complete

echo "== 3. prompt v2: every ticket is re-classified once"
uv run enrich plan --prompt v2
uv run enrich run --prompt v2 --require-complete

(cd warehouse/dbt && uv run dbt build --profiles-dir . -q)
uv run enrich report
uv run enrich eval --prompt v1 --prompt v2 --save-baseline
