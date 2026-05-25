from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from google_connect.runners.calendar_reader import list_events
from google_connect.runners.drive_reader import extract_file_text
from google_connect.runners.gmail_incremental import list_message_details
from google_connect.runners.common import google_service
from google_connect.runners.tasks_reader import filter_tasklists
from google_connect.runners.tasks_reader import list_tasks
from google_connect.runners.tasks_writer import resolve_tasklist


class _ExecuteOnce:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _MessagesGet:
    def __init__(self, details):
        self.details = details

    def __call__(self, userId, id, format):  # noqa: N803
        return _ExecuteOnce(self.details[id])


class _MessagesList:
    def __init__(self, pages):
        self.pages = pages
        self.index = 0

    def __call__(self, **kwargs):
        payload = self.pages[self.index]
        self.index += 1
        return _ExecuteOnce(payload)


class GmailServiceStub:
    def __init__(self, pages, details):
        self._pages = pages
        self._details = details
        self._messages_list = _MessagesList(self._pages)
        self._messages_get = _MessagesGet(self._details)

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, **kwargs):
        return self._messages_list(**kwargs)

    def get(self, **kwargs):
        return self._messages_get(**kwargs)


class CalendarServiceStub:
    def __init__(self, pages):
        self.pages = pages
        self.index = 0

    def events(self):
        return self

    def list(self, **kwargs):
        payload = self.pages[self.index]
        self.index += 1
        return _ExecuteOnce(payload)


class DriveFilesStub:
    def __init__(self, export_bytes=None, media_bytes=None):
        self.export_bytes = export_bytes or b""
        self.media_bytes = media_bytes or b""

    def export_media(self, **kwargs):
        return _ExecuteOnce(self.export_bytes)

    def get_media(self, **kwargs):
        return _ExecuteOnce(self.media_bytes)


class DriveServiceStub:
    def __init__(self, export_bytes=None, media_bytes=None):
        self._files = DriveFilesStub(export_bytes=export_bytes, media_bytes=media_bytes)

    def files(self):
        return self._files


class TasksServiceStub:
    def __init__(self, tasklists):
        self._tasklists = tasklists

    def tasklists(self):
        return self

    def tasks(self):
        return self

    def list(self, **kwargs):
        if "tasklist" in kwargs:
            active_only = [task for task in self._tasklists if task.get("status") != "completed"]
            if kwargs.get("showCompleted") is False and kwargs.get("showHidden") is False:
                return _ExecuteOnce({"items": active_only})
        return _ExecuteOnce({"items": self._tasklists})


class RunnerTests(unittest.TestCase):
    def test_gmail_list_fetches_multiple_pages(self) -> None:
        service = GmailServiceStub(
            pages=[
                {"messages": [{"id": "1"}], "nextPageToken": "next"},
                {"messages": [{"id": "2"}]},
            ],
            details={
                "1": {"id": "1", "internalDate": "1000", "payload": {"headers": []}},
                "2": {"id": "2", "internalDate": "2000", "payload": {"headers": []}},
            },
        )
        details = list_message_details(service, "me", "after:0", 10)
        self.assertEqual([item["id"] for item in details], ["1", "2"])

    def test_calendar_list_fetches_multiple_pages(self) -> None:
        service = CalendarServiceStub(
            pages=[
                {"items": [{"id": "a"}], "nextPageToken": "next"},
                {"items": [{"id": "b"}]},
            ]
        )
        events = list_events(service, "primary", "min", "max")
        self.assertEqual([item["id"] for item in events], ["a", "b"])

    def test_drive_text_routes_native_doc_export(self) -> None:
        service = DriveServiceStub(export_bytes=b"native text")
        text = extract_file_text(service, {"id": "doc-1", "mimeType": "application/vnd.google-apps.document"})
        self.assertEqual(text, "native text")

    def test_tasklist_filter_and_resolution(self) -> None:
        tasklists = [{"id": "1", "title": "One"}, {"id": "2", "title": "Two"}]
        self.assertEqual(filter_tasklists(tasklists, ["Two"]), [{"id": "2", "title": "Two"}])
        resolved = resolve_tasklist(TasksServiceStub(tasklists), "Two", 100)
        self.assertEqual(resolved["id"], "2")

    def test_tasks_list_only_requests_active_items(self) -> None:
        service = TasksServiceStub(
            [
                {"id": "1", "status": "needsAction"},
                {"id": "2", "status": "completed"},
            ]
        )
        tasks = list_tasks(service, "tasklist-1", 25)
        self.assertEqual([task["id"] for task in tasks], ["1"])

    def test_google_service_uses_env_auth_mode(self) -> None:
        config = type(
            "Config",
            (),
            {
                "google": type(
                    "Google",
                    (),
                    {
                        "credentials_path": "creds.json",
                        "token_path": "token.json",
                        "scopes": ["scope-a"],
                    },
                )(),
            },
        )()
        original = os.environ.get("GOOGLE_CONNECT_AUTH_MODE")
        try:
            os.environ["GOOGLE_CONNECT_AUTH_MODE"] = "wsl"
            with patch("google_connect.runners.common.load_credentials", return_value="creds") as mock_load, patch(
                "google_connect.runners.common.build_service", return_value="service"
            ) as mock_build:
                service = google_service(config, "gmail", "v1")
        finally:
            if original is None:
                os.environ.pop("GOOGLE_CONNECT_AUTH_MODE", None)
            else:
                os.environ["GOOGLE_CONNECT_AUTH_MODE"] = original

        mock_load.assert_called_once_with("creds.json", "token.json", ["scope-a"], auth_mode="wsl")
        mock_build.assert_called_once_with("gmail", "v1", "creds")
        self.assertEqual(service, "service")
