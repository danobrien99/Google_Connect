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
- Gmail send/compose is blocked by policy and cannot be enabled through scopes.
- All write runners require explicit config enablement plus confirmation flags.

## MCP stdio entrypoints

For local agent integration inside the same container:

```bash
python -m google_connect.mcp.read_server
python -m google_connect.mcp.write_server
```

Recommended deployment pattern:

- Always run the read server
- Only expose the write server to trusted agents
- Keep `GOOGLE_CONNECT_ENABLE_WRITES=false` unless mutations are intentionally required
- Use allowlists for calendars, spreadsheets, and tasklists before enabling write tools
- State files live under `state/`.
- Logs live under `logs/`.
- EKG must be reachable at the configured base URL.
- Keep may require Workspace admin approval for the requested scopes.
