#!/usr/bin/env bash
set -euo pipefail
python -m google_connect.runners.sheets_writer --config config/google_connect.yaml "$@"
