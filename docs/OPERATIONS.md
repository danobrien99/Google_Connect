# Operations

## Cron examples

```cron
# Sheets + calendar every morning
15 6 * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_sheets_reader.sh >> logs/cron.log 2>&1
30 6 * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_calendar_reader.sh >> logs/cron.log 2>&1

# Incremental Gmail every 20 minutes
*/20 * * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_gmail_incremental.sh >> logs/cron.log 2>&1

# Drive + Keep every hour
5 * * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_drive_reader.sh >> logs/cron.log 2>&1
10 * * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_keep_reader.sh >> logs/cron.log 2>&1

# Tasks sync every 30 minutes
*/30 * * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_tasks_reader.sh >> logs/cron.log 2>&1
```

## Notes

- Gmail, Calendar, Drive, and Keep runners are read-only.
- Calendar writes support create, update, and delete.
- Sheets writes support range update and row append.
- Tasks writes are limited to create, update, and complete.
- Tasks reads only request active tasks by default.
- Gmail send/compose is blocked by policy and cannot be enabled through scopes.
- All write runners require explicit config enablement plus confirmation flags.

## WSL and OpenClaw auth

Use the WSL/OpenClaw auth mode when the repo is running inside WSL and the operator will complete consent in a Windows browser.

```bash
export GOOGLE_CONNECT_AUTH_MODE=wsl
python -m google_connect.product.bootstrap_auth_wsl --config config/google_connect.yaml --fresh
```

Equivalent shared bootstrap command:

```bash
python -m google_connect.product.bootstrap_auth --config config/google_connect.yaml --auth-mode wsl --fresh
```

Behavior:

- The auth helper prints a Google auth URL and does not attempt to open a Linux browser.
- It listens for the callback inside WSL using the installed-app localhost redirect.
- If the callback never reaches WSL, paste the final `http://localhost...` URL or just the `code` value once to finish the token exchange.

## MCP stdio entrypoints

For local agent integration inside the same container:

```bash
python -m google_connect.mcp.read_server
python -m google_connect.mcp.write_server
```

Recommended deployment pattern:

- Always run the read server
- Only expose the write server to trusted agents
- Set `GOOGLE_CONNECT_AUTH_MODE=wsl` before starting MCP in WSL/OpenClaw if you want startup auth to use the Windows-browser-compatible flow
- Keep `GOOGLE_CONNECT_ENABLE_WRITES=false` unless mutations are intentionally required
- Use allowlists for calendars, spreadsheets, and tasklists before enabling write tools
- State files live under the project-root `state/` directory.
- Logs live under `logs/`.
- EKG must be reachable at the configured base URL.
- Keep may require Workspace admin approval for the requested scopes.
