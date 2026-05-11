from __future__ import annotations

import io
import unittest

from docx import Document as DocxDocument

from google_connect.gmail import normalize_gmail_thread
from google_connect.transformers import (
    extract_drive_text,
    gmail_message_to_document,
    keep_note_to_document,
    sheet_rows_to_document,
    task_to_document,
)


class TransformerTests(unittest.TestCase):
    def test_sheet_document_id_is_stable(self) -> None:
        rows = [{"name": "A"}]
        first = sheet_rows_to_document("google_sheets", "sheet-1", "contacts", rows)
        second = sheet_rows_to_document("google_sheets", "sheet-1", "contacts", rows)
        self.assertEqual(first["document_id"], second["document_id"])

    def test_gmail_uses_provider_id(self) -> None:
        document = gmail_message_to_document({"id": "gmail-123", "payload": {"headers": []}})
        self.assertEqual(document["document_id"], "gmail:gmail-123")

    def test_gmail_document_uses_readable_body(self) -> None:
        detail = {
            "id": "gmail-123",
            "threadId": "thread-123",
            "snippet": "snippet",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Hello"},
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "To", "value": "Bob <bob@example.com>"},
                ],
                "mimeType": "text/plain",
                "body": {"data": "aGVsbG8gYm9keQ"},
            },
        }
        thread = normalize_gmail_thread({"id": "thread-123", "messages": [detail]}, include_html=False)
        document = gmail_message_to_document(detail, thread)
        self.assertIn("hello body", document["text"])
        self.assertNotIn('"payload"', document["text"])
        self.assertEqual(document["metadata"]["thread_context"]["participants"], ["alice@example.com", "bob@example.com"])

    def test_keep_note_renders_checklist(self) -> None:
        document = keep_note_to_document(
            {
                "name": "notes/abc",
                "title": "Groceries",
                "list": {"listItems": [{"text": {"text": "Milk"}, "checked": True}]},
            }
        )
        self.assertIn("[x] Milk", document["text"])

    def test_task_document_includes_tasklist(self) -> None:
        document = task_to_document({"id": "task-1", "title": "Follow up"}, {"id": "list-1", "title": "My Tasks"})
        self.assertEqual(document["document_id"], "google-task:list-1:task-1")

    def test_docx_text_extraction(self) -> None:
        handle = io.BytesIO()
        document = DocxDocument()
        document.add_paragraph("hello world")
        document.save(handle)
        extracted = extract_drive_text(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            handle.getvalue(),
        )
        self.assertIn("hello world", extracted)
