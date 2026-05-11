#!/usr/bin/env bash
set -euo pipefail
python -m google_connect.runners.drive_reader --config config/google_connect.yaml "$@"
