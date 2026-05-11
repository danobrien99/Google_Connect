from __future__ import annotations

from pathlib import Path
from typing import Any

from google_connect.config import AppConfig, load_config
from google_connect.ekg_client import EkgClient
from google_connect.google_auth import build_service, load_credentials
from google_connect.logging_utils import setup_logging
from google_connect.state import StateStore


def bootstrap(config_path: str | Path, runner_name: str) -> tuple[AppConfig, EkgClient, StateStore, Any]:
    config = load_config(config_path)
    logger = setup_logging(config.runtime.log_dir, runner_name)
    state = StateStore(config.runtime.state_dir)
    ekg = EkgClient(config.ekg.base_url.rstrip("/"), config.ekg.webhook_secret)
    return config, ekg, state, logger


def google_service(config: AppConfig, api_name: str, version: str):
    creds = load_credentials(config.google.credentials_path, config.google.token_path, config.google.scopes)
    return build_service(api_name, version, creds)


def runner_summary(name: str, summary: dict[str, Any], logger: Any) -> dict[str, Any]:
    logger.info("%s summary=%s", name, summary)
    print(summary)
    return summary
