from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from google_connect.config import load_config


class LoadConfigTests(unittest.TestCase):
    def test_env_overrides_yaml(self) -> None:
        original = os.environ.get("GOOGLE_CONNECT_EKG_BASE_URL")
        os.environ["GOOGLE_CONNECT_EKG_BASE_URL"] = "http://override.local"
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                config_dir = root / "config"
                config_dir.mkdir()
                (root / ".env").write_text("")
                config_path = config_dir / "google_connect.yaml"
                config_path.write_text(
                    textwrap.dedent(
                        """
                        ekg:
                          base_url: http://yaml.local
                        google:
                          credentials_path: creds.json
                          token_path: token.json
                          scopes: [scope-a]
                          sheets:
                            spreadsheet_id: sheet
                            contacts_range: Contacts!A:Z
                            deals_range: Deals!A:Z
                        runtime:
                          state_dir: state
                          log_dir: logs
                        """
                    ).strip()
                )
                config = load_config(config_path)
                self.assertEqual(config.ekg.base_url, "http://override.local")
        finally:
            if original is None:
                os.environ.pop("GOOGLE_CONNECT_EKG_BASE_URL", None)
            else:
                os.environ["GOOGLE_CONNECT_EKG_BASE_URL"] = original

    def test_forbidden_gmail_send_scope_is_rejected(self) -> None:
        original = os.environ.get("GOOGLE_CONNECT_GOOGLE_SCOPES")
        os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = "https://www.googleapis.com/auth/gmail.send"
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                config_dir = root / "config"
                config_dir.mkdir()
                (root / ".env").write_text("")
                config_path = config_dir / "google_connect.yaml"
                config_path.write_text(
                    textwrap.dedent(
                        """
                        ekg:
                          base_url: http://yaml.local
                        google:
                          credentials_path: creds.json
                          token_path: token.json
                          scopes:
                            - https://www.googleapis.com/auth/gmail.readonly
                          sheets:
                            spreadsheet_id: sheet
                            contacts_range: Contacts!A:Z
                            deals_range: Deals!A:Z
                        runtime:
                          state_dir: state
                          log_dir: logs
                        """
                    ).strip()
                )
                with self.assertRaises(ValueError):
                    load_config(config_path)
        finally:
            if original is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_SCOPES", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = original

    def test_gmail_compose_scope_is_allowed(self) -> None:
        original = os.environ.get("GOOGLE_CONNECT_GOOGLE_SCOPES")
        os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = "https://www.googleapis.com/auth/gmail.compose"
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                config_dir = root / "config"
                config_dir.mkdir()
                (root / ".env").write_text("")
                config_path = config_dir / "google_connect.yaml"
                config_path.write_text(
                    textwrap.dedent(
                        """
                        ekg:
                          base_url: http://yaml.local
                        google:
                          credentials_path: creds.json
                          token_path: token.json
                          scopes:
                            - https://www.googleapis.com/auth/gmail.readonly
                          sheets:
                            spreadsheet_id: sheet
                            contacts_range: Contacts!A:Z
                            deals_range: Deals!A:Z
                        runtime:
                          state_dir: state
                          log_dir: logs
                        """
                    ).strip()
                )
                config = load_config(config_path)
                self.assertIn("https://www.googleapis.com/auth/gmail.compose", config.google.scopes)
        finally:
            if original is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_SCOPES", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = original
