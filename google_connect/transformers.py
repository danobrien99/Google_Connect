from __future__ import annotations

import hashlib
import io
import json
from typing import Any

from docx import Document as DocxDocument
from pypdf import PdfReader

from google_connect.gmail import normalize_gmail_message


def stable_document_id(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"{prefix}:{hashlib.sha1(raw).hexdigest()[:16]}"


def sheet_rows_to_document(
    source_name: str,
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    body = json.dumps({"sheet": sheet_name, "rows": rows}, indent=2, default=str)
    metadata = {
        "source_name": source_name,
        "spreadsheet_id": spreadsheet_id,
        "sheet_name": sheet_name,
        "record_count": len(rows),
    }
    return {
        "document_id": f"google-sheet:{spreadsheet_id}:{sheet_name}",
        "title": f"Google Sheet import: {sheet_name}",
        "text": body,
        "document_class": "crm_sheet_export",
        "document_traits": ["google_sheets", sheet_name.lower().replace(" ", "_")],
        "source_type": "google_sheets",
        "artifact_type": "sheet_rows",
        "mime_type": "application/json",
        "metadata": metadata,
    }


def gmail_message_to_document(detail: dict[str, Any], thread: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_gmail_message(detail)
    header_lines = [
        f"Subject: {normalized['subject'] or 'Gmail message'}",
        f"From: {normalized['from'] or 'Unknown'}",
        f"To: {normalized['to'] or 'Unknown'}",
    ]
    if normalized.get("cc"):
        header_lines.append(f"Cc: {normalized['cc']}")
    if normalized.get("reply_to"):
        header_lines.append(f"Reply-To: {normalized['reply_to']}")
    text_sections = ["\n".join(header_lines)]
    if normalized.get("body_text"):
        text_sections.append(normalized["body_text"])
    elif normalized.get("snippet"):
        text_sections.append(normalized["snippet"])

    metadata = {
        "gmail_message_id": normalized.get("message_id"),
        "thread_id": normalized.get("thread_id"),
        "history_id": normalized.get("history_id"),
        "internal_date": normalized.get("internal_date"),
        "label_ids": normalized.get("label_ids", []),
        "from": normalized.get("from"),
        "to": normalized.get("to"),
        "cc": normalized.get("cc"),
        "bcc": normalized.get("bcc"),
        "reply_to": normalized.get("reply_to"),
        "subject": normalized.get("subject"),
        "snippet": normalized.get("snippet"),
        "body_source": normalized.get("body_source"),
        "has_attachments": normalized.get("has_attachments"),
        "attachments": normalized.get("attachments", []),
        "gmail_permalink": normalized.get("gmail_permalink"),
    }
    if thread:
        metadata["thread_context"] = {
            "subject": thread.get("subject"),
            "participants": thread.get("participants", []),
            "labels_union": thread.get("labels_union", []),
            "message_count": thread.get("message_count"),
            "first_message_at": thread.get("first_message_at"),
            "last_message_at": thread.get("last_message_at"),
        }
    return {
        "document_id": f"gmail:{normalized.get('message_id')}",
        "title": normalized.get("subject") or "Gmail message",
        "text": "\n\n".join(section for section in text_sections if section.strip()),
        "document_class": "email_message",
        "document_traits": ["gmail", "business_communication"],
        "source_type": "gmail",
        "artifact_type": "email",
        "mime_type": "text/plain",
        "metadata": metadata,
    }


def calendar_events_to_document(events: list[dict[str, Any]], calendar_id: str) -> dict[str, Any]:
    metadata = {
        "calendar_id": calendar_id,
        "event_count": len(events),
    }
    return {
        "document_id": f"google-calendar:{calendar_id}",
        "title": f"Google Calendar events for {calendar_id}",
        "text": json.dumps(events, indent=2, default=str),
        "document_class": "calendar_event_batch",
        "document_traits": ["google_calendar", "meetings"],
        "source_type": "google_calendar",
        "artifact_type": "event_batch",
        "mime_type": "application/json",
        "metadata": metadata,
    }


def calendar_event_to_document(event: dict[str, Any], calendar_id: str) -> dict[str, Any]:
    metadata = {
        "calendar_id": calendar_id,
        "event_id": event.get("id"),
        "status": event.get("status"),
        "html_link": event.get("htmlLink"),
        "start": event.get("start"),
        "end": event.get("end"),
        "attendees": event.get("attendees", []),
    }
    return {
        "document_id": f"google-calendar:{calendar_id}:{event.get('id')}",
        "title": event.get("summary") or "Google Calendar event",
        "text": json.dumps(event, indent=2, default=str),
        "document_class": "calendar_event",
        "document_traits": ["google_calendar", "meeting"],
        "source_type": "google_calendar",
        "artifact_type": "event",
        "mime_type": "application/json",
        "metadata": metadata,
    }


def sheet_range_to_document(
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]],
    operation: str,
) -> dict[str, Any]:
    metadata = {
        "spreadsheet_id": spreadsheet_id,
        "range": range_name,
        "operation": operation,
        "row_count": len(values),
    }
    return {
        "document_id": f"google-sheet-range:{spreadsheet_id}:{range_name}",
        "title": f"Google Sheet range update: {range_name}",
        "text": json.dumps({"range": range_name, "values": values}, indent=2, default=str),
        "document_class": "sheet_range_update",
        "document_traits": ["google_sheets", "sheet_update"],
        "source_type": "google_sheets",
        "artifact_type": "range_update",
        "mime_type": "application/json",
        "metadata": metadata,
    }


def drive_file_to_document(file_metadata: dict[str, Any], extracted_text: str) -> dict[str, Any]:
    owners = [owner.get("emailAddress") or owner.get("displayName") for owner in file_metadata.get("owners", [])]
    metadata = {
        "drive_file_id": file_metadata.get("id"),
        "name": file_metadata.get("name"),
        "mime_type": file_metadata.get("mimeType"),
        "modified_time": file_metadata.get("modifiedTime"),
        "owners": owners,
        "web_view_link": file_metadata.get("webViewLink"),
        "parents": file_metadata.get("parents", []),
    }
    return {
        "document_id": f"google-drive:{file_metadata.get('id')}",
        "title": file_metadata.get("name") or "Google Drive document",
        "text": extracted_text,
        "document_class": "workspace_document",
        "document_traits": ["google_drive", "document"],
        "source_type": "google_drive",
        "artifact_type": "document",
        "mime_type": "text/plain",
        "metadata": metadata,
    }


def keep_note_to_document(note: dict[str, Any]) -> dict[str, Any]:
    body_text = (((note.get("body") or {}).get("text") or {}).get("text") or "").strip()
    list_items = []
    for item in ((note.get("list") or {}).get("listItems") or []):
        list_items.append(
            {
                "text": ((item.get("text") or {}).get("text") or "").strip(),
                "checked": item.get("checked"),
            }
        )
    checklist_lines = [f"- [{'x' if item['checked'] else ' '}] {item['text']}" for item in list_items if item["text"]]
    rendered_text = "\n".join(part for part in [note.get("title"), body_text, *checklist_lines] if part)
    metadata = {
        "keep_note_name": note.get("name"),
        "title": note.get("title"),
        "labels": [label.get("name") for label in note.get("labels", [])],
        "permissions": [permission.get("role") for permission in note.get("permissions", [])],
        "create_time": note.get("createTime"),
        "update_time": note.get("updateTime"),
        "trashed": bool(note.get("trashed")),
        "trash_time": note.get("trashTime"),
        "checklist_count": len(list_items),
    }
    return {
        "document_id": f"google-keep:{str(note.get('name', '')).replace('/', ':')}",
        "title": note.get("title") or "Google Keep note",
        "text": rendered_text or json.dumps(note, indent=2, default=str),
        "document_class": "note_document",
        "document_traits": ["google_keep", "note"],
        "source_type": "google_keep",
        "artifact_type": "note",
        "mime_type": "text/plain",
        "metadata": metadata,
    }


def task_to_document(task: dict[str, Any], tasklist: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "task_id": task.get("id"),
        "tasklist_id": tasklist.get("id"),
        "tasklist_title": tasklist.get("title"),
        "status": task.get("status"),
        "due": task.get("due"),
        "completed": task.get("completed"),
        "updated": task.get("updated"),
        "parent": task.get("parent"),
        "position": task.get("position"),
    }
    lines = [
        f"Task: {task.get('title') or '(untitled)'}",
        f"Task List: {tasklist.get('title') or tasklist.get('id')}",
    ]
    if task.get("notes"):
        lines.extend(["", task["notes"]])
    return {
        "document_id": f"google-task:{tasklist.get('id')}:{task.get('id')}",
        "title": task.get("title") or "Google Task",
        "text": "\n".join(lines),
        "document_class": "task_item",
        "document_traits": ["google_tasks", "task"],
        "source_type": "google_tasks",
        "artifact_type": "task",
        "mime_type": "text/plain",
        "metadata": metadata,
    }


def extract_drive_text(mime_type: str, content: bytes) -> str:
    if mime_type in {"text/plain", "text/markdown"}:
        return content.decode("utf-8", errors="replace")
    if mime_type == "application/pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        document = DocxDocument(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    raise ValueError(f"unsupported drive mime type: {mime_type}")
