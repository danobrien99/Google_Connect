from __future__ import annotations

import io
import json
import sys
import unittest
from unittest.mock import patch

from google_connect.product import bootstrap_auth
from google_connect.product import bootstrap_auth_wsl


class BootstrapAuthTests(unittest.TestCase):
    def _config_stub(self):
        return type(
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

    def test_bootstrap_auth_forwards_auth_mode(self) -> None:
        with (
            patch.object(sys, "argv", ["bootstrap_auth", "--config", "config/google_connect.yaml", "--auth-mode", "wsl", "--fresh"]),
            patch("google_connect.product.bootstrap_auth.load_config", return_value=self._config_stub()),
            patch("google_connect.product.bootstrap_auth.load_credentials") as mock_load,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            mock_load.return_value = type("Creds", (), {"valid": True})()
            bootstrap_auth.main()

        mock_load.assert_called_once_with(
            "creds.json",
            "token.json",
            ["scope-a"],
            force_fresh=True,
            auth_mode="wsl",
        )
        payload = json.loads(stdout.getvalue().strip())
        self.assertEqual(payload["auth_mode"], "wsl")

    def test_bootstrap_auth_wsl_uses_wsl_mode(self) -> None:
        with (
            patch.object(sys, "argv", ["bootstrap_auth_wsl", "--config", "config/google_connect.yaml"]),
            patch("google_connect.product.bootstrap_auth_wsl.load_config", return_value=self._config_stub()),
            patch("google_connect.product.bootstrap_auth_wsl.load_credentials") as mock_load,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            mock_load.return_value = type("Creds", (), {"valid": True})()
            bootstrap_auth_wsl.main()

        mock_load.assert_called_once_with(
            "creds.json",
            "token.json",
            ["scope-a"],
            force_fresh=False,
            auth_mode="wsl",
        )
        payload = json.loads(stdout.getvalue().strip())
        self.assertEqual(payload["auth_mode"], "wsl")
