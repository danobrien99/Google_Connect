from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from google_connect.config import load_config


class LoadConfigTests(unittest.TestCase):
    def test_env_overrides_yaml(self) -> None:
        original_base_url = os.environ.get("GOOGLE_CONNECT_EKG_BASE_URL")
        original_scopes = os.environ.get("GOOGLE_CONNECT_GOOGLE_SCOPES")
        os.environ["GOOGLE_CONNECT_EKG_BASE_URL"] = "http://override.local"
        os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = "scope-a"
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
            if original_base_url is None:
                os.environ.pop("GOOGLE_CONNECT_EKG_BASE_URL", None)
            else:
                os.environ["GOOGLE_CONNECT_EKG_BASE_URL"] = original_base_url
            if original_scopes is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_SCOPES", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = original_scopes

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

    def test_gmail_compose_scope_is_removed_when_flag_disabled(self) -> None:
        original_scopes = os.environ.get("GOOGLE_CONNECT_GOOGLE_SCOPES")
        original_include = os.environ.get("GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE")
        os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = "https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.compose"
        os.environ["GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE"] = "false"
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
                self.assertEqual(config.google.scopes, ["https://www.googleapis.com/auth/gmail.readonly"])
        finally:
            if original_scopes is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_SCOPES", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = original_scopes
            if original_include is None:
                os.environ.pop("GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE", None)
            else:
                os.environ["GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE"] = original_include

    def test_gmail_compose_scope_is_added_when_flag_enabled(self) -> None:
        original_scopes = os.environ.get("GOOGLE_CONNECT_GOOGLE_SCOPES")
        original_include = os.environ.get("GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE")
        os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = "https://www.googleapis.com/auth/gmail.readonly"
        os.environ["GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE"] = "true"
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
                self.assertEqual(
                    config.google.scopes,
                    [
                        "https://www.googleapis.com/auth/gmail.readonly",
                        "https://www.googleapis.com/auth/gmail.compose",
                    ],
                )
        finally:
            if original_scopes is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_SCOPES", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = original_scopes
            if original_include is None:
                os.environ.pop("GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE", None)
            else:
                os.environ["GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE"] = original_include

    def test_runtime_root_resolves_relative_paths(self) -> None:
        original_runtime_root = os.environ.get("GOOGLE_CONNECT_RUNTIME_ROOT")
        original_scopes = os.environ.get("GOOGLE_CONNECT_GOOGLE_SCOPES")
        original_credentials_path = os.environ.get("GOOGLE_CONNECT_GOOGLE_CREDENTIALS_PATH")
        original_token_path = os.environ.get("GOOGLE_CONNECT_GOOGLE_TOKEN_PATH")
        original_state_dir = os.environ.get("GOOGLE_CONNECT_STATE_DIR")
        original_log_dir = os.environ.get("GOOGLE_CONNECT_LOG_DIR")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                runtime_root = root / "runtime"
                runtime_root.mkdir()
                os.environ["GOOGLE_CONNECT_RUNTIME_ROOT"] = str(runtime_root)
                os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = "https://www.googleapis.com/auth/gmail.readonly"
                os.environ["GOOGLE_CONNECT_GOOGLE_CREDENTIALS_PATH"] = "creds.json"
                os.environ["GOOGLE_CONNECT_GOOGLE_TOKEN_PATH"] = "state/token.json"
                os.environ["GOOGLE_CONNECT_STATE_DIR"] = "state"
                os.environ["GOOGLE_CONNECT_LOG_DIR"] = "logs"
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
                          token_path: state/token.json
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
                self.assertEqual(config.google.credentials_path, (runtime_root / "creds.json").resolve())
                self.assertEqual(config.google.token_path, (runtime_root / "state/token.json").resolve())
                self.assertEqual(config.runtime.state_dir, (runtime_root / "state").resolve())
                self.assertEqual(config.runtime.log_dir, (runtime_root / "logs").resolve())
        finally:
            if original_runtime_root is None:
                os.environ.pop("GOOGLE_CONNECT_RUNTIME_ROOT", None)
            else:
                os.environ["GOOGLE_CONNECT_RUNTIME_ROOT"] = original_runtime_root
            if original_scopes is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_SCOPES", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = original_scopes
            if original_credentials_path is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_CREDENTIALS_PATH", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_CREDENTIALS_PATH"] = original_credentials_path
            if original_token_path is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_TOKEN_PATH", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_TOKEN_PATH"] = original_token_path
            if original_state_dir is None:
                os.environ.pop("GOOGLE_CONNECT_STATE_DIR", None)
            else:
                os.environ["GOOGLE_CONNECT_STATE_DIR"] = original_state_dir
            if original_log_dir is None:
                os.environ.pop("GOOGLE_CONNECT_LOG_DIR", None)
            else:
                os.environ["GOOGLE_CONNECT_LOG_DIR"] = original_log_dir

    def test_load_config_ignores_repo_root_dotenv_when_runtime_root_is_set(self) -> None:
        original_scopes = os.environ.get("GOOGLE_CONNECT_GOOGLE_SCOPES")
        original_include = os.environ.get("GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE")
        original_runtime_root = os.environ.get("GOOGLE_CONNECT_RUNTIME_ROOT")
        try:
            os.environ.pop("GOOGLE_CONNECT_GOOGLE_SCOPES", None)
            os.environ["GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE"] = "false"
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                config_dir = root / "config"
                config_dir.mkdir()
                runtime_root = root / "runtime"
                runtime_root.mkdir()
                os.environ["GOOGLE_CONNECT_RUNTIME_ROOT"] = str(runtime_root)
                (root / ".env").write_text(
                    "GOOGLE_CONNECT_GOOGLE_SCOPES=https://www.googleapis.com/auth/gmail.modify,https://www.googleapis.com/auth/tasks\n"
                )
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
                            - https://www.googleapis.com/auth/tasks.readonly
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
                self.assertEqual(
                    config.google.scopes,
                    [
                        "https://www.googleapis.com/auth/gmail.readonly",
                        "https://www.googleapis.com/auth/tasks.readonly",
                    ],
                )
        finally:
            if original_scopes is None:
                os.environ.pop("GOOGLE_CONNECT_GOOGLE_SCOPES", None)
            else:
                os.environ["GOOGLE_CONNECT_GOOGLE_SCOPES"] = original_scopes
            if original_include is None:
                os.environ.pop("GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE", None)
            else:
                os.environ["GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE"] = original_include
            if original_runtime_root is None:
                os.environ.pop("GOOGLE_CONNECT_RUNTIME_ROOT", None)
            else:
                os.environ["GOOGLE_CONNECT_RUNTIME_ROOT"] = original_runtime_root
