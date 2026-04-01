from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import yaml


@dataclass
class EkgConfig:
    base_url: str
    webhook_secret: str | None = None


@dataclass
class SheetsConfig:
    spreadsheet_id: str
    contacts_range: str
    deals_range: str


@dataclass
class GoogleConfig:
    credentials_path: Path
    token_path: Path
    scopes: list[str]
    gmail_user_id: str
    calendar_id: str
    sheets: SheetsConfig


@dataclass
class RuntimeConfig:
    state_dir: Path
    log_dir: Path
    lookback_days: int
    max_messages: int
    extraction_mode: str
    source_owner: str


@dataclass
class AppConfig:
    ekg: EkgConfig
    google: GoogleConfig
    runtime: RuntimeConfig


def load_config(path: str | Path) -> AppConfig:
    data = yaml.safe_load(Path(path).read_text())
    return AppConfig(
        ekg=EkgConfig(**data["ekg"]),
        google=GoogleConfig(
            credentials_path=Path(data["google"]["credentials_path"]),
            token_path=Path(data["google"]["token_path"]),
            scopes=list(data["google"]["scopes"]),
            gmail_user_id=data["google"].get("gmail_user_id", "me"),
            calendar_id=data["google"].get("calendar_id", "primary"),
            sheets=SheetsConfig(**data["google"]["sheets"]),
        ),
        runtime=RuntimeConfig(
            state_dir=Path(data["runtime"]["state_dir"]),
            log_dir=Path(data["runtime"]["log_dir"]),
            lookback_days=int(data["runtime"].get("lookback_days", 30)),
            max_messages=int(data["runtime"].get("max_messages", 250)),
            extraction_mode=data["runtime"].get("extraction_mode", "hybrid_llm_validated"),
            source_owner=data["runtime"].get("source_owner", "unknown"),
        ),
    )
