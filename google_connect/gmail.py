from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.utils import getaddresses
from html import unescape
from typing import Any


def get_gmail_thread(service: Any, user_id: str, thread_id: str) -> dict[str, Any]:
    return service.users().threads().get(userId=user_id, id=thread_id, format="full").execute()


def extract_gmail_message_body(message_detail: dict[str, Any]) -> dict[str, str]:
    payload = message_detail.get("payload", {})
    plain_parts: list[str] = []
    html_parts: list[str] = []
    _collect_body_parts(payload, plain_parts, html_parts)

    text = "\n\n".join(part for part in plain_parts if part.strip()).strip()
    html = "\n\n".join(part for part in html_parts if part.strip()).strip()

    if text:
        return {"text": text, "html": html, "body_source": "text/plain"}
    if html:
        return {"text": unescape(html), "html": html, "body_source": "text/html"}

    snippet = (message_detail.get("snippet") or "").strip()
    if snippet:
        return {"text": snippet, "html": "", "body_source": "snippet_fallback"}

    return {"text": "", "html": "", "body_source": "empty"}


def normalize_gmail_message(message_detail: dict[str, Any], *, include_html: bool = True) -> dict[str, Any]:
    payload = message_detail.get("payload", {})
    headers = _normalize_headers(payload.get("headers", []))
    body = extract_gmail_message_body(message_detail)
    attachments = _collect_attachments(payload)

    return {
        "message_id": message_detail.get("id"),
        "thread_id": message_detail.get("threadId"),
        "history_id": message_detail.get("historyId"),
        "internal_date": _internal_date_to_iso(message_detail.get("internalDate")),
        "label_ids": list(message_detail.get("labelIds", [])),
        "headers": headers,
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "bcc": headers.get("bcc", ""),
        "reply_to": headers.get("reply-to", ""),
        "subject": headers.get("subject", ""),
        "snippet": (message_detail.get("snippet") or "").strip(),
        "body_text": body["text"],
        "body_html": body["html"] if include_html else "",
        "body_source": body["body_source"],
        "has_attachments": bool(attachments),
        "attachments": attachments,
        "gmail_permalink": _gmail_message_permalink(message_detail.get("id")),
    }


def normalize_gmail_thread(thread_detail: dict[str, Any], *, include_html: bool = True) -> dict[str, Any]:
    normalized_messages = [
        normalize_gmail_message(message, include_html=include_html) for message in thread_detail.get("messages", [])
    ]

    subject = next((message["subject"] for message in normalized_messages if message.get("subject")), "")
    snippets = [message.get("snippet", "") for message in normalized_messages if message.get("snippet")]
    labels_union = sorted({label_id for message in normalized_messages for label_id in message.get("label_ids", [])})
    message_dates = [message["internal_date"] for message in normalized_messages if message.get("internal_date")]
    history_id = thread_detail.get("historyId") or next(
        (message["history_id"] for message in reversed(normalized_messages) if message.get("history_id")),
        None,
    )

    return {
        "thread_id": thread_detail.get("id"),
        "history_id": history_id,
        "message_count": len(normalized_messages),
        "subject": subject,
        "participants": _extract_participants(normalized_messages),
        "labels_union": labels_union,
        "first_message_at": min(message_dates) if message_dates else None,
        "last_message_at": max(message_dates) if message_dates else None,
        "snippet": snippets[-1] if snippets else "",
        "messages": normalized_messages,
    }


def thread_summary_from_normalized(normalized_thread: dict[str, Any]) -> dict[str, Any]:
    return {
        "thread_id": normalized_thread.get("thread_id"),
        "subject": normalized_thread.get("subject", ""),
        "snippet": normalized_thread.get("snippet", ""),
        "last_message_at": normalized_thread.get("last_message_at"),
        "participants": normalized_thread.get("participants", []),
        "message_count": normalized_thread.get("message_count", 0),
    }


def _collect_body_parts(part: dict[str, Any], plain_parts: list[str], html_parts: list[str]) -> None:
    mime_type = (part.get("mimeType") or "").lower()
    body = part.get("body", {})
    body_data = body.get("data")

    if mime_type == "text/plain" and body_data:
        plain_parts.append(_decode_base64url_to_text(body_data))
    elif mime_type == "text/html" and body_data:
        html_parts.append(_decode_base64url_to_text(body_data))

    for child in part.get("parts", []) or []:
        _collect_body_parts(child, plain_parts, html_parts)


def _collect_attachments(part: dict[str, Any]) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    _walk_attachments(part, attachments)
    return attachments


def _walk_attachments(part: dict[str, Any], attachments: list[dict[str, Any]]) -> None:
    body = part.get("body", {})
    attachment_id = body.get("attachmentId")
    filename = part.get("filename") or ""

    if attachment_id or filename:
        attachments.append(
            {
                "filename": filename,
                "mime_type": part.get("mimeType", ""),
                "attachment_id": attachment_id,
                "size": body.get("size", 0) or 0,
            }
        )

    for child in part.get("parts", []) or []:
        _walk_attachments(child, attachments)


def _normalize_headers(headers: list[dict[str, Any]]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for header in headers:
        name = (header.get("name") or "").strip().lower()
        if name:
            normalized[name] = (header.get("value") or "").strip()
    return normalized


def _extract_participants(messages: list[dict[str, Any]]) -> list[str]:
    raw_addresses: list[str] = []
    for message in messages:
        raw_addresses.extend(
            value
            for value in (
                message.get("from", ""),
                message.get("to", ""),
                message.get("cc", ""),
                message.get("bcc", ""),
                message.get("reply_to", ""),
            )
            if value
        )

    participants: list[str] = []
    seen: set[str] = set()
    for _, email in getaddresses(raw_addresses):
        normalized = email.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            participants.append(normalized)
    return participants


def _decode_base64url_to_text(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))
    return decoded.decode("utf-8", errors="replace")


def _internal_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (TypeError, ValueError):
        return None
    return dt.isoformat()


def _gmail_message_permalink(message_id: str | None) -> str | None:
    if not message_id:
        return None
    return f"https://mail.google.com/mail/u/0/#all/{message_id}"
