from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google_connect.runner_utils import ingest_document
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.transformers import calendar_event_to_document
from google_connect.write_guards import require_delete_allowed, require_write_allowed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--summary", required=True)
    create_parser.add_argument("--start", required=True, help="ISO datetime without timezone, e.g. 2026-04-20T17:00")
    create_parser.add_argument("--end", help="ISO datetime without timezone")
    create_parser.add_argument("--duration-minutes", type=int, default=60)
    create_parser.add_argument("--timezone", default="UTC")
    create_parser.add_argument("--description")
    create_parser.add_argument("--location")
    create_parser.add_argument("--confirm-write", action="store_true")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--event-id", required=True)
    update_parser.add_argument("--summary")
    update_parser.add_argument("--start", help="ISO datetime without timezone")
    update_parser.add_argument("--end", help="ISO datetime without timezone")
    update_parser.add_argument("--duration-minutes", type=int)
    update_parser.add_argument("--timezone", default="UTC")
    update_parser.add_argument("--description")
    update_parser.add_argument("--location")
    update_parser.add_argument("--confirm-write", action="store_true")

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("--event-id", required=True)
    delete_parser.add_argument("--confirm-delete", action="store_true")
    return parser


def parse_local_datetime(raw_value: str, timezone_name: str) -> datetime:
    tz = ZoneInfo(timezone_name)
    return datetime.fromisoformat(raw_value).replace(tzinfo=tz)


def refresh_event_document(service, ekg, extraction_mode: str, calendar_id: str, event_id: str) -> dict:
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    document = calendar_event_to_document(event, calendar_id)
    ingest_result = ingest_document(ekg, document, extraction_mode)
    return {"event": event, "document_id": document["document_id"], "ingest_result": ingest_result}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config, ekg, _state, logger = bootstrap(args.config, "calendar_writer")
    service = google_service(config, "calendar", "v3")
    calendar_id = config.google.calendar_id

    if args.command == "create":
        require_write_allowed(config, "calendar", "create", calendar_id, args.confirm_write, logger)
        start_dt = parse_local_datetime(args.start, args.timezone)
        end_dt = parse_local_datetime(args.end, args.timezone) if args.end else start_dt + timedelta(minutes=args.duration_minutes)
        body = {
            "summary": args.summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": args.timezone},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": args.timezone},
        }
        if args.description is not None:
            body["description"] = args.description
        if args.location is not None:
            body["location"] = args.location
        created = service.events().insert(calendarId=calendar_id, body=body).execute()
        refreshed = refresh_event_document(service, ekg, config.runtime.extraction_mode, calendar_id, created["id"])
        runner_summary("calendar_writer", {"ok": True, "action": "create", "event_id": created["id"], **refreshed}, logger)
        return

    if args.command == "update":
        require_write_allowed(config, "calendar", "update", calendar_id, args.confirm_write, logger)
        event = service.events().get(calendarId=calendar_id, eventId=args.event_id).execute()
        if args.summary is not None:
            event["summary"] = args.summary
        if args.description is not None:
            event["description"] = args.description
        if args.location is not None:
            event["location"] = args.location
        if args.start is not None:
            start_dt = parse_local_datetime(args.start, args.timezone)
            end_dt = parse_local_datetime(args.end, args.timezone) if args.end else start_dt + timedelta(minutes=args.duration_minutes or 60)
            event["start"] = {"dateTime": start_dt.isoformat(), "timeZone": args.timezone}
            event["end"] = {"dateTime": end_dt.isoformat(), "timeZone": args.timezone}
        updated = service.events().update(calendarId=calendar_id, eventId=args.event_id, body=event).execute()
        refreshed = refresh_event_document(service, ekg, config.runtime.extraction_mode, calendar_id, updated["id"])
        runner_summary("calendar_writer", {"ok": True, "action": "update", "event_id": updated["id"], **refreshed}, logger)
        return

    require_delete_allowed(config, "calendar", calendar_id, args.confirm_delete, logger)
    service.events().delete(calendarId=calendar_id, eventId=args.event_id).execute()
    runner_summary("calendar_writer", {"ok": True, "action": "delete", "event_id": args.event_id}, logger)


if __name__ == "__main__":
    main()
