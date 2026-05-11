#!/usr/bin/env bash
set -euo pipefail
python -m google_connect.runners.tasks_reader --config config/google_connect.yaml "$@"
