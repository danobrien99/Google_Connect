# Google_Connect

Python-first Google Workspace connectors for Enterprise_KG.

## What it does

- Reads Google Sheets contacts/deals data with stable document IDs
- Reads Gmail incrementally with pagination-safe cursor handling
- Backfills Gmail history in batches
- Creates Gmail drafts without send capability
- Reads Google Calendar events with full pagination
- Reads Google Drive documents incrementally
- Reads Google Keep notes incrementally
- Reads and writes Google Tasks, then refreshes task state into Enterprise_KG
- Ingests documents into Enterprise_KG and triggers extraction
- Provides thin n8n wrappers and cron-ready shell entrypoints

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cp .env.example .env
```

Fill in `.env` or `config/google_connect.yaml` with:

- Google OAuth client credentials path
- Enterprise_KG base URL and optional webhook secret
- Optional Drive folder/tasklist filters
- Google Keep enablement only after the required Keep scopes are approved

## OAuth setup and re-auth

The OAuth flow is triggered automatically the first time the package calls `load_credentials()`.

To force a fresh auth flow and regenerate the token:

```bash
cd /path/to/Google_Connect
source .venv/bin/activate
rm -f state/google-token.json
python - <<'PY'
from google_connect.config import load_config
from google_connect.google_auth import load_credentials

cfg = load_config("config/google_connect.yaml")
load_credentials(cfg.google.credentials_path, cfg.google.token_path, cfg.google.scopes)
print("Auth complete")
print("Token saved to:", cfg.google.token_path)
print("Scopes:", cfg.google.scopes)
PY
```

To force a fresh browser grant without reusing the cached token, set `GOOGLE_CONNECT_FORCE_FRESH_OAUTH=true` before starting the MCP server, or run:

```bash
python -m google_connect.product.bootstrap_auth --config config/google_connect.yaml --fresh
```

For WSL/OpenClaw on Windows, use the dedicated WSL auth path:

```bash
python -m google_connect.product.bootstrap_auth_wsl --config config/google_connect.yaml --fresh
```

Or select the same flow from the shared bootstrap command:

```bash
python -m google_connect.product.bootstrap_auth --config config/google_connect.yaml --auth-mode wsl --fresh
```

Notes:

- Make sure the configured scopes match what you want before running the flow.
- For Gmail draft support, include `https://www.googleapis.com/auth/gmail.compose`.
- Do not include `https://www.googleapis.com/auth/gmail.send` or `https://mail.google.com/`; those are rejected by policy.
- Desktop auth opens your local browser, waits for the local OAuth redirect, and completes the token exchange without requiring copy/paste.
- If the browser callback fails, check that your Google OAuth client is configured for a loopback redirect URI compatible with installed-app flows.
- A fresh grant requests consent again and uses the current config scopes instead of reusing an older cached token.
- WSL/OpenClaw auth prints a URL for the Windows browser, listens for the callback inside WSL, and falls back to a one-time pasted URL or code if the callback never reaches WSL.
- Restart the MCP servers after re-auth so they pick up the refreshed token.
- The canonical local secret/runtime location is the project-root `state/` directory; `config/state` remains as a compatibility symlink.

## Runners

```bash
python -m google_connect.runners.sheets_reader --config config/google_connect.yaml
python -m google_connect.runners.gmail_incremental --config config/google_connect.yaml
python -m google_connect.runners.gmail_backfill --config config/google_connect.yaml --max-messages 100
python -m google_connect.runners.calendar_reader --config config/google_connect.yaml
python -m google_connect.runners.calendar_writer --config config/google_connect.yaml create --summary "Test" --start 2026-04-20T17:00 --timezone Europe/Berlin --confirm-write
python -m google_connect.runners.drive_reader --config config/google_connect.yaml
python -m google_connect.runners.keep_reader --config config/google_connect.yaml
python -m google_connect.runners.tasks_reader --config config/google_connect.yaml
python -m google_connect.runners.tasks_writer --config config/google_connect.yaml create --tasklist "My Tasks" --title "Follow up" --confirm-write
python -m google_connect.runners.tasks_writer --config config/google_connect.yaml update --tasklist "My Tasks" --task-id TASK_ID --notes "Updated context" --confirm-write
python -m google_connect.runners.tasks_writer --config config/google_connect.yaml complete --tasklist "My Tasks" --task-id TASK_ID --confirm-write
python -m google_connect.runners.sheets_writer --config config/google_connect.yaml update --range Contacts!A2:B2 --values-json '[[\"Alice\",\"alice@example.com\"]]' --confirm-write
python -m google_connect.runners.sheets_writer --config config/google_connect.yaml append --range Contacts!A:B --value "Bob" --value "bob@example.com" --confirm-write
```

## Enterprise_KG integration model

Each runner:

1. normalizes source records into stable document payloads
2. calls `POST /api/ingest/document`
3. calls `POST /api/extract/document`
4. records structured summaries and cursor state

This connector remains document-first. It does not write ontology assertions directly.

## Write guardrails

- Gmail send scope and full-mail scope are forbidden and rejected at config load time.
- All writes are disabled unless `GOOGLE_CONNECT_ENABLE_WRITES=true`.
- Gmail drafts also require `GOOGLE_CONNECT_ENABLE_GMAIL_DRAFTS=true`.
- Calendar, Sheets, and Tasks also require service-specific write toggles.
- Writers require explicit confirmation flags.
- Calendar deletion additionally requires `GOOGLE_CONNECT_ENABLE_CALENDAR_DELETE=true` and `--confirm-delete`.
- Optional allowlists can restrict writes to approved tasklists, calendars, and spreadsheets.

## Operational notes

- `.env` values override YAML config.
- Set `GOOGLE_CONNECT_AUTH_MODE=wsl` in OpenClaw/WSL if browser auth should avoid Linux browser automation.
- Google Keep support is user-OAuth first, but Workspace admin approval may still be required for Keep scopes.
- Drive ingestion is docs-focused in v1: native Google Docs plus supported plain text, PDF, and DOCX files.
- Tasks v1 supports create, update, and complete. Delete is intentionally excluded.

## MCP servers

Two local stdio MCP servers are included for agent use:

- Read-only server:
  - `python -m google_connect.mcp.read_server`
- Write-enabled server:
  - `python -m google_connect.mcp.write_server`

Both servers use the same Google OAuth token/config as the rest of the package. The write server enforces the existing guardrails:

- global write kill switch
- per-service write toggles
- allowlists
- explicit `confirmed=true` arguments on mutation tools

The write server does not expose Gmail send or compose tools, and config loading rejects Gmail send/compose scopes entirely.
The write server exposes Gmail draft creation only. Gmail send is not implemented, and config loading still rejects `gmail.send` and full-mail scopes.
Both MCP servers eagerly load Google credentials on startup so the browser auth flow runs before tool serving begins.
`tasks_list_tasks` defaults to active tasks only so completed tasks do not slow down the list path.

### WSL/OpenClaw runtime

- Set `GOOGLE_CONNECT_AUTH_MODE=wsl` for read/write MCP servers and shell wrappers running inside WSL/OpenClaw.
- The WSL flow prints a Google auth URL instead of trying to launch a Linux browser.
- It listens on a WSL callback port using the existing installed-app `http://localhost` redirect model.
- If Windows-to-WSL localhost callback forwarding fails, paste the returned `http://localhost...` URL or the `code` value once to finish the grant.

See `docs/OPERATIONS.md` for cron and wrapper examples.
