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
class DriveConfig:
    enabled: bool
    folder_ids: list[str]
    query: str
    include_mime_types: list[str]
    page_size: int


@dataclass
class KeepConfig:
    enabled: bool
    page_size: int
    include_trashed: bool


@dataclass
class TasksConfig:
    enabled: bool
    tasklist_filter: list[str]
    default_tasklist: str | None
    page_size: int


@dataclass
class GoogleConfig:
    credentials_path: Path
    token_path: Path
    scopes: list[str]
    gmail_user_id: str
    calendar_id: str
    sheets: SheetsConfig
    drive: DriveConfig
    keep: KeepConfig
    tasks: TasksConfig


@dataclass
class RuntimeConfig:
    state_dir: Path
    log_dir: Path
    lookback_days: int
    max_messages: int
    extraction_mode: str
    source_owner: str


@dataclass
class WriteGuardConfig:
    enable_writes: bool
    gmail_draft_enabled: bool
    calendar_write_enabled: bool
    calendar_delete_enabled: bool
    sheets_write_enabled: bool
    tasks_write_enabled: bool
    writable_tasklists: list[str]
    writable_calendars: list[str]
    writable_spreadsheets: list[str]


@dataclass
class AppConfig:
    ekg: EkgConfig
    google: GoogleConfig
    runtime: RuntimeConfig
    write_guards: WriteGuardConfig


TRUE_VALUES = {"1", "true", "yes", "on"}
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
FORBIDDEN_GMAIL_SCOPES = {
    "https://www.googleapis.com/auth/gmail.send",
    "https://mail.google.com/",
}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _merge_env_file_candidates(config_path: Path) -> None:
    candidates = [config_path.parent / ".env"]
    if not os.environ.get("GOOGLE_CONNECT_RUNTIME_ROOT"):
        candidates.append(config_path.parent.parent / ".env")
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        _load_dotenv(resolved)


def _env_or(data: dict, env_key: str, *path: str, default=None):
    if env_key in os.environ and os.environ[env_key] != "":
        return os.environ[env_key]
    current = data
    for key in path:
        if current is None or key not in current:
            return default
        current = current[key]
    return current if current is not None else default


def _env_bool(data: dict, env_key: str, *path: str, default: bool = False) -> bool:
    value = _env_or(data, env_key, *path, default=default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUE_VALUES


def _env_int(data: dict, env_key: str, *path: str, default: int) -> int:
    return int(_env_or(data, env_key, *path, default=default))


def _env_list(data: dict, env_key: str, *path: str, default: list[str] | None = None) -> list[str]:
    value = _env_or(data, env_key, *path, default=default or [])
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _validate_google_scopes(scopes: list[str]) -> list[str]:
    forbidden = sorted(scope for scope in scopes if scope in FORBIDDEN_GMAIL_SCOPES)
    if forbidden:
        raise ValueError(f"Gmail send/full-mail scopes are forbidden by policy: {', '.join(forbidden)}")
    return scopes


def _resolved_google_scopes(data: dict) -> list[str]:
    scopes = _env_list(data, "GOOGLE_CONNECT_GOOGLE_SCOPES", "google", "scopes")
    include_gmail_compose = _env_bool(
        data,
        "GOOGLE_CONNECT_INCLUDE_GMAIL_COMPOSE_SCOPE",
        default=GMAIL_COMPOSE_SCOPE in scopes,
    )
    normalized = [scope for scope in scopes if scope != GMAIL_COMPOSE_SCOPE]
    if include_gmail_compose:
        normalized.append(GMAIL_COMPOSE_SCOPE)
    return _validate_google_scopes(normalized)


def _resolve_runtime_path(value: str | Path, *, config_path: Path) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw

    runtime_root = os.environ.get("GOOGLE_CONNECT_RUNTIME_ROOT")
    if runtime_root:
        return Path(runtime_root).expanduser().resolve() / raw
    return (config_path.parent / raw).resolve()


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    _merge_env_file_candidates(config_path)
    data = yaml.safe_load(config_path.read_text()) or {}
    google_data = data.get("google", {})

    scopes = _resolved_google_scopes(data)

    return AppConfig(
        ekg=EkgConfig(
            base_url=_env_or(data, "GOOGLE_CONNECT_EKG_BASE_URL", "ekg", "base_url"),
            webhook_secret=_env_or(data, "GOOGLE_CONNECT_EKG_WEBHOOK_SECRET", "ekg", "webhook_secret"),
        ),
        google=GoogleConfig(
            credentials_path=_resolve_runtime_path(
                _env_or(data, "GOOGLE_CONNECT_GOOGLE_CREDENTIALS_PATH", "google", "credentials_path"),
                config_path=config_path,
            ),
            token_path=_resolve_runtime_path(
                _env_or(data, "GOOGLE_CONNECT_GOOGLE_TOKEN_PATH", "google", "token_path"),
                config_path=config_path,
            ),
            scopes=scopes,
            gmail_user_id=_env_or(data, "GOOGLE_CONNECT_GMAIL_USER_ID", "google", "gmail_user_id", default="me"),
            calendar_id=_env_or(data, "GOOGLE_CONNECT_CALENDAR_ID", "google", "calendar_id", default="primary"),
            sheets=SheetsConfig(
                spreadsheet_id=_env_or(data, "GOOGLE_CONNECT_SHEETS_SPREADSHEET_ID", "google", "sheets", "spreadsheet_id"),
                contacts_range=_env_or(data, "GOOGLE_CONNECT_SHEETS_CONTACTS_RANGE", "google", "sheets", "contacts_range"),
                deals_range=_env_or(data, "GOOGLE_CONNECT_SHEETS_DEALS_RANGE", "google", "sheets", "deals_range"),
            ),
            drive=DriveConfig(
                enabled=_env_bool(data, "GOOGLE_CONNECT_DRIVE_ENABLED", "google", "drive", "enabled", default=True),
                folder_ids=_env_list(data, "GOOGLE_CONNECT_DRIVE_FOLDER_IDS", "google", "drive", "folder_ids"),
                query=_env_or(data, "GOOGLE_CONNECT_DRIVE_QUERY", "google", "drive", "query", default=""),
                include_mime_types=_env_list(
                    data,
                    "GOOGLE_CONNECT_DRIVE_INCLUDE_MIME_TYPES",
                    "google",
                    "drive",
                    "include_mime_types",
                ),
                page_size=_env_int(data, "GOOGLE_CONNECT_DRIVE_PAGE_SIZE", "google", "drive", "page_size", default=100),
            ),
            keep=KeepConfig(
                enabled=_env_bool(data, "GOOGLE_CONNECT_KEEP_ENABLED", "google", "keep", "enabled", default=False),
                page_size=_env_int(data, "GOOGLE_CONNECT_KEEP_PAGE_SIZE", "google", "keep", "page_size", default=50),
                include_trashed=_env_bool(
                    data,
                    "GOOGLE_CONNECT_KEEP_INCLUDE_TRASHED",
                    "google",
                    "keep",
                    "include_trashed",
                    default=False,
                ),
            ),
            tasks=TasksConfig(
                enabled=_env_bool(data, "GOOGLE_CONNECT_TASKS_ENABLED", "google", "tasks", "enabled", default=True),
                tasklist_filter=_env_list(
                    data,
                    "GOOGLE_CONNECT_TASKS_TASKLIST_FILTER",
                    "google",
                    "tasks",
                    "tasklist_filter",
                ),
                default_tasklist=_env_or(
                    data,
                    "GOOGLE_CONNECT_TASKS_DEFAULT_TASKLIST",
                    "google",
                    "tasks",
                    "default_tasklist",
                ),
                page_size=_env_int(data, "GOOGLE_CONNECT_TASKS_PAGE_SIZE", "google", "tasks", "page_size", default=100),
            ),
        ),
        runtime=RuntimeConfig(
            state_dir=_resolve_runtime_path(
                _env_or(data, "GOOGLE_CONNECT_STATE_DIR", "runtime", "state_dir", default="state"),
                config_path=config_path,
            ),
            log_dir=_resolve_runtime_path(
                _env_or(data, "GOOGLE_CONNECT_LOG_DIR", "runtime", "log_dir", default="logs"),
                config_path=config_path,
            ),
            lookback_days=_env_int(data, "GOOGLE_CONNECT_LOOKBACK_DAYS", "runtime", "lookback_days", default=30),
            max_messages=_env_int(data, "GOOGLE_CONNECT_MAX_MESSAGES", "runtime", "max_messages", default=250),
            extraction_mode=_env_or(
                data,
                "GOOGLE_CONNECT_EXTRACTION_MODE",
                "runtime",
                "extraction_mode",
                default="hybrid_llm_validated",
            ),
            source_owner=_env_or(data, "GOOGLE_CONNECT_SOURCE_OWNER", "runtime", "source_owner", default="unknown"),
        ),
        write_guards=WriteGuardConfig(
            enable_writes=_env_bool(data, "GOOGLE_CONNECT_ENABLE_WRITES", "write_guards", "enable_writes", default=False),
            gmail_draft_enabled=_env_bool(
                data, "GOOGLE_CONNECT_ENABLE_GMAIL_DRAFTS", "write_guards", "gmail_draft_enabled", default=False
            ),
            calendar_write_enabled=_env_bool(
                data, "GOOGLE_CONNECT_ENABLE_CALENDAR_WRITES", "write_guards", "calendar_write_enabled", default=False
            ),
            calendar_delete_enabled=_env_bool(
                data, "GOOGLE_CONNECT_ENABLE_CALENDAR_DELETE", "write_guards", "calendar_delete_enabled", default=False
            ),
            sheets_write_enabled=_env_bool(
                data, "GOOGLE_CONNECT_ENABLE_SHEETS_WRITES", "write_guards", "sheets_write_enabled", default=False
            ),
            tasks_write_enabled=_env_bool(
                data, "GOOGLE_CONNECT_ENABLE_TASKS_WRITES", "write_guards", "tasks_write_enabled", default=False
            ),
            writable_tasklists=_env_list(
                data, "GOOGLE_CONNECT_WRITABLE_TASKLISTS", "write_guards", "writable_tasklists"
            ),
            writable_calendars=_env_list(
                data, "GOOGLE_CONNECT_WRITABLE_CALENDARS", "write_guards", "writable_calendars"
            ),
            writable_spreadsheets=_env_list(
                data, "GOOGLE_CONNECT_WRITABLE_SPREADSHEETS", "write_guards", "writable_spreadsheets"
            ),
        ),
    )
