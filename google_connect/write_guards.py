from __future__ import annotations

from typing import Any


def _is_target_allowed(target: str, allowlist: list[str]) -> bool:
    return not allowlist or target in allowlist


def log_write_attempt(logger: Any, service: str, action: str, target: str, confirmed: bool) -> None:
    logger.info("write_attempt service=%s action=%s target=%s confirmed=%s", service, action, target, confirmed)


def require_write_allowed(config: Any, service: str, action: str, target: str, confirmed: bool, logger: Any) -> None:
    log_write_attempt(logger, service, action, target, confirmed)
    if not config.write_guards.enable_writes:
        raise PermissionError("writes are disabled by GOOGLE_CONNECT_ENABLE_WRITES=false")
    if not confirmed:
        raise PermissionError(f"{service} {action} requires explicit confirmation")

    if service == "gmail":
        if action != "draft":
            raise PermissionError(f"gmail action is not supported by policy: {action}")
        if not config.write_guards.gmail_draft_enabled:
            raise PermissionError("gmail draft creation is disabled by policy")
        return

    if service == "calendar":
        if not config.write_guards.calendar_write_enabled:
            raise PermissionError("calendar writes are disabled by policy")
        if not _is_target_allowed(target, config.write_guards.writable_calendars):
            raise PermissionError(f"calendar target is not allowlisted: {target}")
        return

    if service == "sheets":
        if not config.write_guards.sheets_write_enabled:
            raise PermissionError("sheets writes are disabled by policy")
        if not _is_target_allowed(target, config.write_guards.writable_spreadsheets):
            raise PermissionError(f"spreadsheet target is not allowlisted: {target}")
        return

    if service == "tasks":
        if not config.write_guards.tasks_write_enabled:
            raise PermissionError("tasks writes are disabled by policy")
        if not _is_target_allowed(target, config.write_guards.writable_tasklists):
            raise PermissionError(f"tasklist target is not allowlisted: {target}")
        return

    raise PermissionError(f"unknown write service: {service}")


def require_delete_allowed(config: Any, service: str, target: str, confirmed: bool, logger: Any) -> None:
    log_write_attempt(logger, service, "delete", target, confirmed)
    if service != "calendar":
        raise PermissionError(f"delete is not supported for service: {service}")
    if not config.write_guards.enable_writes:
        raise PermissionError("writes are disabled by GOOGLE_CONNECT_ENABLE_WRITES=false")
    if not config.write_guards.calendar_delete_enabled:
        raise PermissionError("calendar delete is disabled by policy")
    if not _is_target_allowed(target, config.write_guards.writable_calendars):
        raise PermissionError(f"calendar target is not allowlisted: {target}")
    if not confirmed:
        raise PermissionError("calendar delete requires explicit confirmation")
