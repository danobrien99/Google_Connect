# Google_Connect

Python-first Google data connectors for Enterprise_KG.

## What it does

- Reads Google Sheets contacts/deals data
- Reads Gmail incrementally using persisted state
- Backfills Gmail history in batches
- Reads Google Calendar events and attendee context
- Ingests documents into Enterprise_KG
- Triggers Enterprise_KG document extraction
- Produces thin n8n wrappers and cron-ready shell entrypoints

## Layout

- `google_connect/` - package source
- `google_connect/runners/` - CLI runners
- `google_connect/n8n/` - thin n8n wrapper workflows
- `config/` - sample config files
- `state/` - persisted cursors/checkpoints
- `scripts/` - cron-friendly shell wrappers
- `logs/` - runtime logs

## Quick start

1. Create venv and install:

```bash
cd Google_Connect
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

2. Copy env file:

```bash
cp .env.example .env
```

3. Fill in:
- Google OAuth/service-account credentials path(s)
- Enterprise_KG base URL
- Optional webhook secret

4. Run a job:

```bash
python -m google_connect.runners.sheets_reader --config config/google_connect.yaml
python -m google_connect.runners.gmail_incremental --config config/google_connect.yaml
python -m google_connect.runners.gmail_backfill --config config/google_connect.yaml --max-messages 100
python -m google_connect.runners.calendar_reader --config config/google_connect.yaml
```

## Enterprise_KG integration model

Each runner:
1. normalizes source records into document payloads
2. calls `POST /api/ingest/document`
3. calls `POST /api/extract/document`
4. records structured summary counts and state

This aligns to current upstream Enterprise_KG API routes.

## n8n wrappers

Import workflows in `google_connect/n8n/` and set environment/credentials as needed. They are wrappers around the Python runners, not business logic containers.

## Cron examples

See `docs/OPERATIONS.md`.
