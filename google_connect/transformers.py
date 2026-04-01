from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def stable_document_id(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"{prefix}:{hashlib.sha1(raw).hexdigest()[:16]}"


def sheet_rows_to_document(source_name: str, sheet_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    body = json.dumps({"sheet": sheet_name, "rows": rows}, indent=2, default=str)
    metadata = {
        "source_name": source_name,
        "sheet_name": sheet_name,
        "record_count": len(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "document_id": stable_document_id(f"google-sheet:{sheet_name}", metadata | {"rows": rows}),
        "title": f"Google Sheet import: {sheet_name}",
        "text": body,
        "document_class": "crm_sheet_export",
        "document_traits": ["google_sheets", sheet_name.lower().replace(' ', '_')],
        "source_type": "google_sheets",
        "artifact_type": "sheet_rows",
        "mime_type": "application/json",
        "metadata": metadata,
    }


def gmail_message_to_document(message: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    payload = detail.get("payload", {})
    headers = {h.get('name','').lower(): h.get('value','') for h in payload.get('headers', [])}
    snippet = detail.get('snippet', '')
    text = json.dumps({"message": detail, "snippet": snippet}, indent=2, default=str)
    metadata = {
        "gmail_message_id": detail.get("id"),
        "thread_id": detail.get("threadId"),
        "from": headers.get("from"),
        "to": headers.get("to"),
        "cc": headers.get("cc"),
        "subject": headers.get("subject"),
        "internal_date": detail.get("internalDate"),
    }
    return {
        "document_id": stable_document_id("gmail", metadata),
        "title": headers.get("subject") or "Gmail message",
        "text": text,
        "document_class": "email_message",
        "document_traits": ["gmail", "business_communication"],
        "source_type": "gmail",
        "artifact_type": "email",
        "mime_type": "application/json",
        "metadata": metadata,
    }


def calendar_events_to_document(events: list[dict[str, Any]], calendar_id: str) -> dict[str, Any]:
    metadata = {
        "calendar_id": calendar_id,
        "event_count": len(events),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "document_id": stable_document_id("google-calendar", {"calendar_id": calendar_id, "events": events}),
        "title": f"Google Calendar events for {calendar_id}",
        "text": json.dumps(events, indent=2, default=str),
        "document_class": "calendar_event_batch",
        "document_traits": ["google_calendar", "meetings"],
        "source_type": "google_calendar",
        "artifact_type": "event_batch",
        "mime_type": "application/json",
        "metadata": metadata,
    }
