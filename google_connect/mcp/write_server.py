from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from google_connect.mcp.backend import WorkspaceBackend


mcp = FastMCP("Google Connect Write Server", json_response=True)
backend = WorkspaceBackend()


@mcp.tool()
def gmail_create_draft(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    confirmed: bool = False,
) -> dict:
    """Create a Gmail draft without sending it."""
    return backend.gmail_create_draft(to=to, subject=subject, body=body, cc=cc, bcc=bcc, confirmed=confirmed)


@mcp.tool()
def calendar_create_event(
    summary: str,
    start: str,
    timezone_name: str = "UTC",
    end: str | None = None,
    duration_minutes: int = 60,
    description: str | None = None,
    location: str | None = None,
    confirmed: bool = False,
) -> dict:
    """Create a calendar event on the configured calendar."""
    return backend.calendar_create_event(
        summary=summary,
        start=start,
        timezone_name=timezone_name,
        end=end,
        duration_minutes=duration_minutes,
        description=description,
        location=location,
        confirmed=confirmed,
    )


@mcp.tool()
def calendar_update_event(
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    timezone_name: str = "UTC",
    end: str | None = None,
    duration_minutes: int | None = None,
    description: str | None = None,
    location: str | None = None,
    confirmed: bool = False,
) -> dict:
    """Update a calendar event by event ID."""
    return backend.calendar_update_event(
        event_id=event_id,
        summary=summary,
        start=start,
        timezone_name=timezone_name,
        end=end,
        duration_minutes=duration_minutes,
        description=description,
        location=location,
        confirmed=confirmed,
    )


@mcp.tool()
def calendar_delete_event(event_id: str, confirmed: bool = False) -> dict:
    """Delete a calendar event by event ID."""
    return backend.calendar_delete_event(event_id=event_id, confirmed=confirmed)


@mcp.tool()
def sheets_update_range(range_name: str, values: list[list[str]], spreadsheet_id: str | None = None, confirmed: bool = False) -> dict:
    """Update a Google Sheets range."""
    return backend.sheets_update_range(range_name=range_name, values=values, spreadsheet_id=spreadsheet_id, confirmed=confirmed)


@mcp.tool()
def sheets_append_row(range_name: str, values: list[str], spreadsheet_id: str | None = None, confirmed: bool = False) -> dict:
    """Append a row to a Google Sheets range."""
    return backend.sheets_append_row(range_name=range_name, values=values, spreadsheet_id=spreadsheet_id, confirmed=confirmed)


@mcp.tool()
def tasks_create_task(
    tasklist: str,
    title: str,
    notes: str | None = None,
    due: str | None = None,
    parent: str | None = None,
    confirmed: bool = False,
) -> dict:
    """Create a Google Task in the specified tasklist."""
    return backend.tasks_create_task(tasklist_ref=tasklist, title=title, notes=notes, due=due, parent=parent, confirmed=confirmed)


@mcp.tool()
def tasks_update_task(
    tasklist: str,
    task_id: str,
    title: str | None = None,
    notes: str | None = None,
    due: str | None = None,
    parent: str | None = None,
    confirmed: bool = False,
) -> dict:
    """Update a Google Task in the specified tasklist."""
    return backend.tasks_update_task(
        tasklist_ref=tasklist,
        task_id=task_id,
        title=title,
        notes=notes,
        due=due,
        parent=parent,
        confirmed=confirmed,
    )


@mcp.tool()
def tasks_complete_task(tasklist: str, task_id: str, confirmed: bool = False) -> dict:
    """Mark a Google Task complete."""
    return backend.tasks_complete_task(tasklist_ref=tasklist, task_id=task_id, confirmed=confirmed)


if __name__ == "__main__":
    mcp.run()
