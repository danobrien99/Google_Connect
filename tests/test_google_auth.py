from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from google_connect.google_auth import _run_installed_flow
from google_connect.google_auth import load_credentials


class GoogleAuthTests(unittest.TestCase):
    def test_run_installed_flow_uses_local_browser_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_path = Path(tmpdir) / "client.json"
            credentials_path.write_text(json.dumps({"installed": {"redirect_uris": ["http://localhost"]}}))

            flow = MagicMock()
            credentials = MagicMock()
            flow.run_local_server.return_value = credentials

            with patch("google_connect.google_auth.InstalledAppFlow.from_client_secrets_file", return_value=flow) as mock_factory:
                result = _run_installed_flow(credentials_path, ["scope-a"])

        mock_factory.assert_called_once_with(str(credentials_path), ["scope-a"])
        flow.run_local_server.assert_called_once_with(port=0, prompt="consent", include_granted_scopes="true")
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
                result = load_credentials(credentials_path, token_path, ["scope-a"], force_fresh=True)

        mock_from_file.assert_not_called()
        mock_factory.assert_called_once_with(str(credentials_path), ["scope-a"])
        flow.run_local_server.assert_called_once_with(port=0, prompt="consent", include_granted_scopes="true")
        self.assertIs(result, credentials)
