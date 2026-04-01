# Operations

## Cron examples

```cron
# Sheets + calendar every morning
15 6 * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_sheets_reader.sh >> logs/cron.log 2>&1
30 6 * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_calendar_reader.sh >> logs/cron.log 2>&1

# Incremental Gmail every 20 minutes
*/20 * * * * cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_gmail_incremental.sh >> logs/cron.log 2>&1

# Backfill on demand only (example disabled)
# 0 2 * * 0 cd /root/.openclaw/workspace/Google_Connect && bash scripts/run_gmail_backfill.sh --max-messages 500 >> logs/cron.log 2>&1
```

## Notes

- Gmail runners are read-only and do not send email.
- State files live under `state/`.
- Logs live under `logs/`.
- EKG must be running and reachable at configured base URL.
