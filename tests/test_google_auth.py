from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError
from google_connect.google_auth import AUTH_MODE_DESKTOP
from google_connect.google_auth import _run_installed_flow
from google_connect.google_auth import _run_wsl_installed_flow
from google_connect.google_auth import load_credentials


class _FakeCallbackServer:
    response_to_set: str | None = None

    def __init__(self, address, handler_cls):
        self.server_port = 8765
        self.authorization_response = None
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_app(self, app):
        self.app = app

    def handle_request(self):
        self.authorization_response = self.response_to_set


class GoogleAuthTests(unittest.TestCase):
    def test_run_installed_flow_uses_local_browser_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_path = Path(tmpdir) / "client.json"
            credentials_path.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}))

            flow = MagicMock()
            credentials = MagicMock()
            flow.run_local_server.return_value = credentials

            with patch("google_connect.google_auth.InstalledAppFlow.from_client_secrets_file", return_value=flow) as mock_factory:
                result = _run_installed_flow(credentials_path, ["scope-a"], AUTH_MODE_DESKTOP)

        mock_factory.assert_called_once_with(str(credentials_path), ["scope-a"])
        flow.run_local_server.assert_called_once_with(port=0, prompt="consent", include_granted_scopes="true")
        self.assertIs(result, credentials)

    def test_run_wsl_flow_fetches_token_from_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_path = Path(tmpdir) / "client.json"
            credentials_path.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}))

            flow = MagicMock()
            credentials = MagicMock()
            flow.credentials = credentials
            flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth", "state-1")
            _FakeCallbackServer.response_to_set = "http://localhost:8765/?state=state-1&code=callback-code"

            with (
                patch("google_connect.google_auth.InstalledAppFlow.from_client_secrets_file", return_value=flow),
                patch("google_connect.google_auth._SingleRequestCallbackServer", _FakeCallbackServer),
                patch("builtins.input") as mock_input,
            ):
                result = _run_wsl_installed_flow(credentials_path, ["scope-a"], timeout_seconds=15)

        flow.authorization_url.assert_called_once_with(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )
        flow.fetch_token.assert_called_once_with(authorization_response="http://localhost:8765/?state=state-1&code=callback-code")
        mock_input.assert_not_called()
        self.assertEqual(flow.redirect_uri, "http://localhost:8765")
        self.assertIs(result, credentials)

    def test_run_wsl_flow_falls_back_to_pasted_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_path = Path(tmpdir) / "client.json"
            credentials_path.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}))

            flow = MagicMock()
            credentials = MagicMock()
            flow.credentials = credentials
            flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth", "state-1")
            _FakeCallbackServer.response_to_set = None

            with (
                patch("google_connect.google_auth.InstalledAppFlow.from_client_secrets_file", return_value=flow),
                patch("google_connect.google_auth._SingleRequestCallbackServer", _FakeCallbackServer),
                patch("builtins.input", return_value="http://localhost:8765/?state=state-1&code=pasted-code"),
            ):
                result = _run_wsl_installed_flow(credentials_path, ["scope-a"], timeout_seconds=15)

        flow.fetch_token.assert_called_once_with(authorization_response="http://localhost:8765/?state=state-1&code=pasted-code")
        self.assertIs(result, credentials)

    def test_run_wsl_flow_falls_back_to_pasted_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_path = Path(tmpdir) / "client.json"
            credentials_path.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}))

            flow = MagicMock()
            credentials = MagicMock()
            flow.credentials = credentials
            flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth", "state-1")
            _FakeCallbackServer.response_to_set = None

            with (
                patch("google_connect.google_auth.InstalledAppFlow.from_client_secrets_file", return_value=flow),
                patch("google_connect.google_auth._SingleRequestCallbackServer", _FakeCallbackServer),
                patch("builtins.input", return_value="raw-code-123"),
            ):
                result = _run_wsl_installed_flow(credentials_path, ["scope-a"], timeout_seconds=15)

        flow.fetch_token.assert_called_once_with(authorization_response="http://localhost:8765?code=raw-code-123")
        self.assertIs(result, credentials)

    def test_load_credentials_force_fresh_ignores_cached_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            credentials_path = tmp_path / "client.json"
            token_path = tmp_path / "token.json"
            credentials_path.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}))
            token_path.write_text("{}")

            flow = MagicMock()
            credentials = MagicMock()
            credentials.valid = True
            credentials.to_json.return_value = "{\"token\": \"fresh\"}"
            flow.run_local_server.return_value = credentials

            with (
                patch("google_connect.google_auth.Credentials.from_authorized_user_file") as mock_from_file,
                patch("google_connect.google_auth.InstalledAppFlow.from_client_secrets_file", return_value=flow) as mock_factory,
            ):
                result = load_credentials(credentials_path, token_path, ["scope-a"], force_fresh=True, auth_mode=AUTH_MODE_DESKTOP)

        mock_from_file.assert_not_called()
        mock_factory.assert_called_once_with(str(credentials_path), ["scope-a"])
        flow.run_local_server.assert_called_once_with(port=0, prompt="consent", include_granted_scopes="true")
        self.assertIs(result, credentials)

    def test_load_credentials_rejects_unsupported_auth_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            credentials_path = tmp_path / "client.json"
            token_path = tmp_path / "token.json"
            credentials_path.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}))

            with self.assertRaises(ValueError):
                load_credentials(credentials_path, token_path, ["scope-a"], auth_mode="bogus")

    def test_load_credentials_falls_back_to_installed_flow_when_refresh_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            credentials_path = tmp_path / "client.json"
            token_path = tmp_path / "token.json"
            credentials_path.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}))
            token_path.write_text("{}")

            cached = MagicMock()
            cached.valid = False
            cached.expired = True
            cached.refresh_token = "refresh-token"
            cached.refresh.side_effect = RefreshError("invalid_scope")

            fresh = MagicMock()
            fresh.valid = True
            fresh.to_json.return_value = "{\"token\": \"fresh\"}"

            with (
                patch("google_connect.google_auth.Credentials.from_authorized_user_file", return_value=cached),
                patch("google_connect.google_auth._run_installed_flow", return_value=fresh) as mock_run_flow,
            ):
                result = load_credentials(credentials_path, token_path, ["scope-a"], auth_mode=AUTH_MODE_DESKTOP)
                written_token = token_path.read_text()

        cached.refresh.assert_called_once()
        mock_run_flow.assert_called_once_with(credentials_path, ["scope-a"], AUTH_MODE_DESKTOP)
        self.assertEqual(written_token, "{\"token\": \"fresh\"}")
        self.assertIs(result, fresh)
