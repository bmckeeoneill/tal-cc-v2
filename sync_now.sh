#!/usr/bin/env bash
# sync_now.sh — immediately pull new emails and run the pipeline
# Usage: bash sync_now.sh
# Run this after forwarding an "account" (or any) email to process it right away.

set -e
cd "$(dirname "$0")"
source venv/bin/activate

echo "=== Ingest ==="
python3 gmail_ingest.py --once

echo ""
echo "=== Pipeline ==="
python3 run_pipeline.py

echo ""
echo "Done. Refresh the app to see changes."
