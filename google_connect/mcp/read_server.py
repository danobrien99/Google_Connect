from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

from mcp.server.fastmcp import FastMCP

from google_connect.mcp.backend import WorkspaceBackend


mcp = FastMCP("Google Connect Read Server", json_response=True)
backend = WorkspaceBackend()


@mcp.tool()
def gmail_get_profile() -> dict:
    """Get the authenticated Gmail profile."""
    return backend.gmail_profile()


@mcp.tool()
def gmail_list_threads(query: str = "", max_results: int = 20) -> list[dict]:
    """List Gmail threads matching an optional query."""
    return backend.gmail_list_threads(query=query, max_results=max_results)


@mcp.tool()
def gmail_get_thread(thread_id: str, include_html: bool = False) -> dict:
    """Get a Gmail thread by thread ID."""
    return backend.gmail_get_thread(thread_id, include_html=include_html)


@mcp.tool()
def calendar_list_events(time_min: str | None = None, time_max: str | None = None, max_results: int = 20) -> list[dict]:
    """List calendar events on the configured calendar within a time range."""
    now = datetime.now(timezone.utc)
    resolved_time_min = time_min or now.isoformat()
    resolved_time_max = time_max or (now + timedelta(days=7)).isoformat()
    return backend.calendar_list_events(resolved_time_min, resolved_time_max, max_results=max_results)


@mcp.tool()
def drive_list_files(query: str = "", page_size: int = 20) -> list[dict]:
    """List Google Drive files."""
    return backend.drive_list_files(query=query, page_size=page_size)


@mcp.tool()
def drive_get_document(file_id: str) -> dict:
    """Get a Google Drive document's metadata and extracted text."""
    return backend.drive_get_document(file_id)


@mcp.tool()
def sheets_get_range(range_name: str, spreadsheet_id: str | None = None) -> dict:
    """Read a range from Google Sheets."""
    return backend.sheets_get_range(range_name=range_name, spreadsheet_id=spreadsheet_id)


@mcp.tool()
def tasks_list_tasklists(max_results: int = 20) -> list[dict]:
    """List Google Tasks tasklists."""
    return backend.tasks_list_tasklists(max_results=max_results)


@mcp.tool()
def tasks_list_tasks(tasklist: str, max_results: int = 50) -> list[dict]:
    """List active tasks in a named tasklist or tasklist ID."""
    return backend.tasks_list_tasks(tasklist_ref=tasklist, max_results=max_results)


@mcp.tool()
def keep_list_notes(page_size: int = 20) -> list[dict]:
    """List Google Keep notes when Keep is enabled and scoped."""
    return backend.keep_list_notes(page_size=page_size)


@mcp.tool()
def runtime_status() -> dict:
    """Return connector/runtime readiness for product onboarding and health checks."""
    return backend.runtime_status()


def main() -> None:
    if host := os.environ.get("GOOGLE_CONNECT_MCP_HOST"):
        mcp.settings.host = host
    if port := os.environ.get("GOOGLE_CONNECT_MCP_PORT"):
        mcp.settings.port = int(port)
    force_fresh = os.environ.get("GOOGLE_CONNECT_FORCE_FRESH_OAUTH", "").strip().lower() in {"1", "true", "yes", "on"}
    backend.credentials(force_fresh=force_fresh)
    mcp.run(
        transport=os.environ.get("GOOGLE_CONNECT_MCP_TRANSPORT", "stdio"),
        mount_path=os.environ.get("GOOGLE_CONNECT_MCP_MOUNT_PATH"),
    )


if __name__ == "__main__":
    main()
