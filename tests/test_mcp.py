from __future__ import annotations

import unittest
from unittest.mock import patch

from google_connect.mcp.backend import WorkspaceBackend
from google_connect.mcp.read_server import mcp as read_mcp
from google_connect.mcp.read_server import gmail_get_thread
from google_connect.mcp.read_server import main as read_main
from google_connect.mcp.write_server import mcp as write_mcp
from google_connect.mcp.write_server import main as write_main


class McpServerTests(unittest.TestCase):
    def test_servers_initialize(self) -> None:
        self.assertIsNotNone(read_mcp)
        self.assertIsNotNone(write_mcp)

    def test_write_server_exposes_gmail_draft_tool(self) -> None:
        self.assertIn("gmail_create_draft", write_mcp._tool_manager._tools)

    def test_read_server_exposes_gmail_thread_tool(self) -> None:
        self.assertIn("gmail_get_thread", read_mcp._tool_manager._tools)

    def test_read_server_exposes_runtime_status_tool(self) -> None:
        self.assertIn("runtime_status", read_mcp._tool_manager._tools)

    def test_gmail_get_thread_passes_include_html(self) -> None:
        with patch("google_connect.mcp.read_server.backend.gmail_get_thread", return_value={"thread_id": "t1"}) as mock_get:
            result = gmail_get_thread("t1", include_html=True)
        mock_get.assert_called_once_with("t1", include_html=True)
        self.assertEqual(result["thread_id"], "t1")

    def test_read_server_main_bootstraps_credentials_before_serving(self) -> None:
        with patch("google_connect.mcp.read_server.backend.credentials") as mock_credentials, patch.object(
            read_mcp, "run"
        ) as mock_run, patch.dict(
            "os.environ",
            {
                "GOOGLE_CONNECT_MCP_TRANSPORT": "stdio",
                "GOOGLE_CONNECT_MCP_MOUNT_PATH": "/mcp",
            },
            clear=False,
        ):
            read_main()
        mock_credentials.assert_called_once_with(force_fresh=False)
        mock_run.assert_called_once_with(transport="stdio", mount_path="/mcp")

    def test_write_server_main_bootstraps_credentials_before_serving(self) -> None:
        with patch("google_connect.mcp.write_server.backend.credentials") as mock_credentials, patch.object(
            write_mcp, "run"
        ) as mock_run, patch.dict(
            "os.environ",
            {
                "GOOGLE_CONNECT_MCP_TRANSPORT": "stdio",
                "GOOGLE_CONNECT_MCP_MOUNT_PATH": "/mcp",
            },
            clear=False,
        ):
            write_main()
        mock_credentials.assert_called_once_with(force_fresh=False)
        mock_run.assert_called_once_with(transport="stdio", mount_path="/mcp")

    def test_read_server_main_can_force_fresh_oauth(self) -> None:
        with patch("google_connect.mcp.read_server.backend.credentials") as mock_credentials, patch.object(
            read_mcp, "run"
        ) as mock_run, patch.dict(
            "os.environ",
            {
                "GOOGLE_CONNECT_MCP_TRANSPORT": "stdio",
                "GOOGLE_CONNECT_MCP_MOUNT_PATH": "/mcp",
                "GOOGLE_CONNECT_FORCE_FRESH_OAUTH": "true",
            },
            clear=False,
        ):
            read_main()
        mock_credentials.assert_called_once_with(force_fresh=True)
        mock_run.assert_called_once_with(transport="stdio", mount_path="/mcp")


class WorkspaceBackendGmailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = WorkspaceBackend()
        self.backend._config = type(
            "Config",
            (),
            {"google": type("Google", (), {"gmail_user_id": "me"})()},
        )()

    def test_gmail_get_thread_returns_normalized_shape(self) -> None:
        raw_thread = {
            "id": "thread-1",
            "messages": [
                {
                    "id": "msg-1",
                    "threadId": "thread-1",
                    "historyId": "history-1",
                    "internalDate": "1715600000000",
                    "labelIds": ["INBOX"],
                    "snippet": "hello",
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "Hello"},
                            {"name": "From", "value": "Alice <alice@example.com>"},
                            {"name": "To", "value": "Bob <bob@example.com>"},
                        ],
                        "mimeType": "text/plain",
                        "body": {"data": "aGVsbG8"},
                    },
                }
            ],
        }
        with patch("google_connect.mcp.backend.get_gmail_thread", return_value=raw_thread), patch.object(
            self.backend, "service", return_value=object()
        ):
            result = self.backend.gmail_get_thread("thread-1", include_html=False)
        self.assertEqual(result["thread_id"], "thread-1")
        self.assertEqual(result["message_count"], 1)
        self.assertEqual(result["messages"][0]["body_html"], "")

    def test_gmail_list_threads_returns_summary_shape(self) -> None:
        response = {"threads": [{"id": "thread-1"}]}
        raw_thread = {
            "id": "thread-1",
            "messages": [
                {
                    "id": "msg-1",
                    "threadId": "thread-1",
                    "historyId": "history-1",
                    "internalDate": "1715600000000",
                    "labelIds": ["INBOX"],
                    "snippet": "hello",
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "Hello"},
                            {"name": "From", "value": "Alice <alice@example.com>"},
                            {"name": "To", "value": "Bob <bob@example.com>"},
                        ],
                        "mimeType": "text/plain",
                        "body": {"data": "aGVsbG8"},
                    },
                }
            ],
        }

        class _Execute:
            def __init__(self, payload):
                self.payload = payload

            def execute(self):
                return self.payload

        class _Threads:
            def list(self, **kwargs):
                return _Execute(response)

        class _Users:
            def threads(self):
                return _Threads()

        class _Service:
            def users(self):
                return _Users()

        with patch("google_connect.mcp.backend.get_gmail_thread", return_value=raw_thread), patch.object(
            self.backend, "service", return_value=_Service()
        ):
            result = self.backend.gmail_list_threads(query="", max_results=10)
        self.assertEqual(result[0]["thread_id"], "thread-1")
        self.assertEqual(sorted(result[0].keys()), ["last_message_at", "message_count", "participants", "snippet", "subject", "thread_id"])

    def test_runtime_status_reports_missing_credentials_cleanly(self) -> None:
        self.backend._config = type(
            "Config",
            (),
            {
                "google": type(
                    "Google",
                    (),
                    {
                        "gmail_user_id": "me",
                        "credentials_path": type("PathLike", (), {"exists": lambda self: False, "__str__": lambda self: "creds.json"})(),
                        "token_path": type("PathLike", (), {"exists": lambda self: False, "__str__": lambda self: "token.json"})(),
                    },
                )(),
            },
        )()
        status = self.backend.runtime_status()
        self.assertFalse(status["credentials_exists"])
        self.assertFalse(status["surfaces"]["gmail"]["ok"])
