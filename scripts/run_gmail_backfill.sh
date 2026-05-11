#!/usr/bin/env bash
set -euo pipefail
python -m google_connect.runners.gmail_backfill --config config/google_connect.yaml "$@"
