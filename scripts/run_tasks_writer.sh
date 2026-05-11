#!/usr/bin/env bash
set -euo pipefail
python -m google_connect.runners.tasks_writer --config config/google_connect.yaml "$@"
