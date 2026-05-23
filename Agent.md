# Agent Guide

This repository is a Python-first Google Workspace connector layer for `RevOS`.
Use it to read Google data, create controlled writes where allowed, and normalize records into EKG documents for ingestion and extraction.

## What This Repo Is For

- Read Google Sheets contacts and deals data with stable document IDs.
- Read Gmail incrementally and backfill message history.
- Read Google Calendar events.
- Read Google Drive documents and extract text from supported file types.
- Read Google Keep notes when Keep is enabled and scoped.
- Read and write Google Tasks with EKG refresh.
- Create Gmail drafts only. Sending mail is intentionally not supported.
- Provide local MCP servers for read-only and write-enabled agent access.
- Provide thin shell wrappers and runner entrypoints for cron or manual execution.

## Core Rule

Treat this repo as a guarded integration layer, not a general-purpose Google API client.
Every mutation must respect the configured write guardrails and explicit confirmation flags.

## Repository Layout

- `google_connect/`
  - Core package code.
  - `config.py` loads YAML plus environment overrides.
  - `google_auth.py` handles OAuth token loading and installed-app browser auth.
  - `mcp/` exposes read/write MCP tools.
  - `runners/` contains CLI entrypoints for reads and writes.
  - `transformers.py` converts source records into EKG document payloads.
  - `runner_utils.py` contains shared bootstrap and ingestion helpers.
  - `write_guards.py` enforces policy and allowlists.
- `scripts/`
  - Shell wrappers for the runner modules.
- `config/google_connect.yaml`
  - Default config checked into the repo.
- `state/`
  - OAuth client and token files live here by default.
- `logs/`
  - Runtime and MCP logs live here.
- `tests/`
  - Unit tests covering config, auth, guards, runners, transformers, and MCP behavior.

## Default Configuration

The default config file is `config/google_connect.yaml`.
The backend also honors `GOOGLE_CONNECT_CONFIG_PATH` if you want to point at another config file.

Config loading rules:

- Environment variables override YAML values.
- `.env` files are merged automatically from the config directory, and from the parent directory when `GOOGLE_CONNECT_RUNTIME_ROOT` is not set.
- Relative runtime paths are resolved against `GOOGLE_CONNECT_RUNTIME_ROOT` when present.
- Otherwise, relative paths resolve relative to the config file location.

Key config fields:

- `ekg.base_url`
- `ekg.webhook_secret`
- `google.credentials_path`
- `google.token_path`
- `google.scopes`
- `google.gmail_user_id`
- `google.calendar_id`
- `google.sheets.spreadsheet_id`
- `google.drive.*`
- `google.keep.*`
- `google.tasks.*`
- `runtime.state_dir`
- `runtime.log_dir`
- `runtime.lookback_days`
- `runtime.max_messages`
- `runtime.extraction_mode`
- `runtime.source_owner`
- `write_guards.*`

## Environment Variables That Matter

### Runtime and config

- `GOOGLE_CONNECT_CONFIG_PATH`
- `GOOGLE_CONNECT_RUNTIME_ROOT`
- `GOOGLE_CONNECT_STATE_DIR`
- `GOOGLE_CONNECT_LOG_DIR`
- `GOOGLE_CONNECT_EKG_BASE_URL`
- `GOOGLE_CONNECT_EKG_WEBHOOK_SECRET`

### Google auth and scopes

- `GOOGLE_CONNECT_GOOGLE_CREDENTIALS_PATH`
- `GOOGLE_CONNECT_GOOGLE_TOKEN_PATH`
- `GOOGLE_CONNECT_GOOGLE_SCOPES`
- `GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE`
- `GOOGLE_CONNECT_GMAIL_USER_ID`
- `GOOGLE_CONNECT_CALENDAR_ID`
- `GOOGLE_CONNECT_SHEETS_SPREADSHEET_ID`
- `GOOGLE_CONNECT_SHEETS_CONTACTS_RANGE`
- `GOOGLE_CONNECT_SHEETS_DEALS_RANGE`
- `GOOGLE_CONNECT_DRIVE_ENABLED`
- `GOOGLE_CONNECT_DRIVE_FOLDER_IDS`
- `GOOGLE_CONNECT_DRIVE_QUERY`
- `GOOGLE_CONNECT_DRIVE_INCLUDE_MIME_TYPES`
- `GOOGLE_CONNECT_DRIVE_PAGE_SIZE`
- `GOOGLE_CONNECT_KEEP_ENABLED`
- `GOOGLE_CONNECT_KEEP_PAGE_SIZE`
- `GOOGLE_CONNECT_KEEP_INCLUDE_TRASHED`
- `GOOGLE_CONNECT_TASKS_ENABLED`
- `GOOGLE_CONNECT_TASKS_TASKLIST_FILTER`
- `GOOGLE_CONNECT_TASKS_DEFAULT_TASKLIST`
- `GOOGLE_CONNECT_TASKS_PAGE_SIZE`

### Write guards

- `GOOGLE_CONNECT_ENABLE_WRITES`
- `GOOGLE_CONNECT_ENABLE_GMAIL_DRAFTS`
- `GOOGLE_CONNECT_ENABLE_CALENDAR_WRITES`
- `GOOGLE_CONNECT_ENABLE_CALENDAR_DELETE`
- `GOOGLE_CONNECT_ENABLE_SHEETS_WRITES`
- `GOOGLE_CONNECT_ENABLE_TASKS_WRITES`
- `GOOGLE_CONNECT_WRITABLE_TASKLISTS`
- `GOOGLE_CONNECT_WRITABLE_CALENDARS`
- `GOOGLE_CONNECT_WRITABLE_SPREADSHEETS`

### MCP server runtime

- `GOOGLE_CONNECT_MCP_HOST`
- `GOOGLE_CONNECT_MCP_PORT`
- `GOOGLE_CONNECT_MCP_TRANSPORT`
- `GOOGLE_CONNECT_MCP_MOUNT_PATH`

## OAuth and Auth Behavior

- The first call that needs credentials triggers the installed-app OAuth flow if a valid token is not already present.
- Tokens are persisted to `google.token_path`.
- The auth helper refreshes expired tokens when possible.
- If the browser callback flow succeeds, restart the MCP servers so they pick up the refreshed token.
- Keep the configured scopes minimal and explicit.
- Gmail send and full-mail scopes are forbidden by config validation.
- `gmail.compose` is optional and controlled by `GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE`.

Forbidden Gmail scopes:

- `https://www.googleapis.com/auth/gmail.send`
- `https://mail.google.com/`

## Read Surfaces

The read MCP server is `python -m google_connect.mcp.read_server`.

Available read tools:

- `gmail_get_profile`
- `gmail_list_threads`
- `gmail_get_thread`
- `calendar_list_events`
- `drive_list_files`
- `drive_get_document`
- `sheets_get_range`
- `tasks_list_tasklists`
- `tasks_list_tasks`
- `keep_list_notes`
- `runtime_status`

Read runners also exist as CLI entrypoints in `google_connect.runners.*` and can be launched with the matching shell scripts in `scripts/`.

## Write Surfaces

The write MCP server is `python -m google_connect.mcp.write_server`.

Available write tools:

- `gmail_create_draft`
- `calendar_create_event`
- `calendar_update_event`
- `calendar_delete_event`
- `sheets_update_range`
- `sheets_append_row`
- `tasks_create_task`
- `tasks_update_task`
- `tasks_complete_task`

Write runners also exist for CLI usage:

- `python -m google_connect.runners.calendar_writer`
- `python -m google_connect.runners.sheets_writer`
- `python -m google_connect.runners.tasks_writer`

## Write Guardrails

Every write path is gated by policy in `google_connect.write_guards`.

Rules to remember:

- `GOOGLE_CONNECT_ENABLE_WRITES` must be true.
- The caller must pass the explicit confirmation flag.
- Gmail only allows draft creation.
- Gmail send is not supported at all.
- Calendar writes require `GOOGLE_CONNECT_ENABLE_CALENDAR_WRITES=true`.
- Calendar delete additionally requires `GOOGLE_CONNECT_ENABLE_CALENDAR_DELETE=true`.
- Sheets writes require `GOOGLE_CONNECT_ENABLE_SHEETS_WRITES=true`.
- Tasks writes require `GOOGLE_CONNECT_ENABLE_TASKS_WRITES=true`.
- Targets must be allowlisted when allowlists are populated.
- If an allowlist is empty, the code treats that as unrestricted for that target category.

Allowlist behavior:

- `writable_calendars` controls calendar mutations.
- `writable_spreadsheets` controls Sheets mutations.
- `writable_tasklists` controls Tasks mutations.

## EKG Integration

Write operations are not just Google mutations.
Most mutations also build an EKG document and attempt a follow-up ingest/extract sync.

Important implications:

- A Google write can succeed even if the EKG sync fails.
- The result payload includes `ekg_sync` so the caller can inspect partial failure.
- Use `runtime.extraction_mode` when invoking ingestion.
- The repo is document-first. It does not write ontology assertions directly.

Shared transformation helpers:

- `transformers.calendar_event_to_document`
- `transformers.sheet_range_to_document`
- `transformers.task_to_document`

## Runtime Status and Health Checks

Use `runtime_status()` for a consolidated readiness check.
It reports:

- config path
- runtime root
- credentials and token existence
- per-surface health for Gmail, Calendar, Drive, and Tasks

If you need to know whether the runtime is actually usable, check this before attempting a workflow that depends on live Google access.

## Data Shape Expectations

Important normalizations in this repo:

- Gmail thread reads return normalized thread summaries.
- Calendar reads return raw event items from Google.
- Drive reads return file metadata, and document reads also include extracted text.
- Sheets reads return the raw values payload.
- Tasks reads and writes resolve tasklists by either title or ID.

## Supported File Types for Drive Text Extraction

Drive ingestion is docs-focused in v1.
Supported types include:

- Google Docs
- plain text
- markdown
- PDF
- DOCX

## Common Commands

### Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cp .env.example .env
```

### Read runners

```bash
python -m google_connect.runners.sheets_reader --config config/google_connect.yaml
python -m google_connect.runners.gmail_incremental --config config/google_connect.yaml
python -m google_connect.runners.gmail_backfill --config config/google_connect.yaml --max-messages 100
python -m google_connect.runners.calendar_reader --config config/google_connect.yaml
python -m google_connect.runners.drive_reader --config config/google_connect.yaml
python -m google_connect.runners.keep_reader --config config/google_connect.yaml
python -m google_connect.runners.tasks_reader --config config/google_connect.yaml
```

### Write runners

```bash
python -m google_connect.runners.calendar_writer --config config/google_connect.yaml create --summary "Test" --start 2026-04-20T17:00 --timezone Europe/Berlin --confirm-write
python -m google_connect.runners.sheets_writer --config config/google_connect.yaml update --range Contacts!A2:B2 --values-json '[["Alice","alice@example.com"]]' --confirm-write
python -m google_connect.runners.tasks_writer --config config/google_connect.yaml create --tasklist "My Tasks" --title "Follow up" --confirm-write
```

### MCP servers

```bash
python -m google_connect.mcp.read_server
python -m google_connect.mcp.write_server
```

## Testing

The tests use the standard library `unittest` style.

Run the full suite with:

```bash
python -m unittest discover -s tests
```

Useful focused tests:

- `tests/test_config.py` for config and env precedence
- `tests/test_guardrails.py` for write policy
- `tests/test_mcp.py` for MCP tool exposure and server bootstrapping
- `tests/test_runners.py` for pagination and resolution behavior
- `tests/test_writers.py` for parser and confirmation behavior

## Troubleshooting Checklist

- If auth fails, inspect the configured credential and token paths first.
- If a runner cannot find credentials, verify the runtime root and whether the token file exists.
- If writes are rejected, check both the global write toggle and the service-specific toggle.
- If a write target is rejected, check the corresponding allowlist.
- If Keep reads fail, verify that Keep is enabled in config and that the requested scopes were approved.
- If the MCP servers seem stale after re-auth, restart them.
- If a config path looks wrong, remember that runtime-root path resolution changes how relative paths are interpreted.

## Editing Expectations For Agents

- Keep changes minimal and aligned with the repo’s existing style.
- Prefer editing code and docs with direct, targeted changes.
- Update tests when behavior changes.
- Do not add Gmail send support.
- Do not weaken the guardrails to make a workflow easier.
- Preserve the document-first EKG ingestion model.

## When You Need More Context

If you are about to change one of these areas, read the relevant source first:

- `google_connect/config.py` for path resolution and env precedence
- `google_connect/write_guards.py` for mutation policy
- `google_connect/mcp/backend.py` for MCP and EKG orchestration
- `google_connect/google_auth.py` for token and browser flow behavior
- `google_connect/runner_utils.py` for ingestion and shared bootstrap
- `tests/` for the expected contract

## Short Version

If you only remember five things:

1. Read access is broad, writes are tightly guarded.
2. Gmail send is forbidden.
3. Every write needs confirmation plus the right service toggle and allowlist.
4. EKG sync is part of the workflow, but it can fail independently from the Google mutation.
5. `runtime_status()` is the quickest sanity check before executing a workflow.
