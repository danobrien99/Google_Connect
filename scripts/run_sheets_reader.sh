#!/usr/bin/env bash
set -euo pipefail
python -m google_connect.runners.sheets_reader --config config/google_connect.yaml "$@"
