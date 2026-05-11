#!/usr/bin/env bash
set -euo pipefail
python -m google_connect.runners.gmail_incremental --config config/google_connect.yaml "$@"
