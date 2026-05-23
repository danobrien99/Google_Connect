from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
import os
from typing import Any
import base64

from google_connect.config import AppConfig, load_config
from google_connect.gmail import get_gmail_thread, normalize_gmail_thread, thread_summary_from_normalized
from google_connect.google_auth import build_service, load_credentials
from google_connect.runners.drive_reader import extract_file_text
from google_connect.runners.tasks_reader import filter_tasklists, list_tasklists, list_tasks
from google_connect.runners.tasks_writer import resolve_tasklist
from google_connect.transformers import calendar_event_to_document, sheet_range_to_document, task_to_document
from google_connect.write_guards import require_delete_allowed, require_write_allowed


DEFAULT_CONFIG_PATH = "config/google_connect.yaml"


@dataclass
class WorkspaceBackend:
    config_path: str = DEFAULT_CONFIG_PATH
    _config: AppConfig | None = None
    _credentials: Any | None = None
    _services: dict[tuple[str, str], Any] | None = None
    _ekg: Any | None = None
    _logger: Any | None = None

    def config(self) -> AppConfig:
        if self._config is None:
            resolved = os.environ.get("GOOGLE_CONNECT_CONFIG_PATH", self.config_path)
            self._config = load_config(resolved)
        return self._config

    def logger(self):
        if self._logger is None:
            from google_connect.logging_utils import setup_logging

            self._logger = setup_logging(self.config().runtime.log_dir, "google_workspace_mcp")
        return self._logger

    def credentials(self, force_fresh: bool = False):
        if self._credentials is None:
            cfg = self.config()
            self._credentials = load_credentials(
                cfg.google.credentials_path,
                cfg.google.token_path,
                cfg.google.scopes,
                force_fresh=force_fresh,
            )
        return self._credentials

    def service(self, api_name: str, version: str):
        if self._services is None:
            self._services = {}
        key = (api_name, version)
        if key not in self._services:
            self._services[key] = build_service(api_name, version, self.credentials())
        return self._services[key]

    def ekg_client(self):
        if self._ekg is None:
            from google_connect.ekg_client import EkgClient

            cfg = self.config()
            self._ekg = EkgClient(cfg.ekg.base_url.rstrip("/"), cfg.ekg.webhook_secret)
        return self._ekg

    def safe_ingest_document(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            from google_connect.runner_utils import ingest_document

            result = ingest_document(self.ekg_client(), document, self.config().runtime.extraction_mode)
            return {"ok": True, "result": result}
        except Exception as exc:  # noqa: BLE001
            self.logger().exception("ekg sync failed document_id=%s", document.get("document_id"))
            return {"ok": False, "error": str(exc), "document_id": document.get("document_id")}

    def gmail_profile(self) -> dict[str, Any]:
        cfg = self.config()
        return self.service("gmail", "v1").users().getProfile(userId=cfg.google.gmail_user_id).execute()

    def runtime_status(self) -> dict[str, Any]:
        cfg = self.config()
        credentials_error: str | None = None
        token_exists = cfg.google.token_path.exists()
        credentials_exists = cfg.google.credentials_path.exists()
        gmail_ok = False
        calendar_ok = False
        drive_ok = False
        tasks_ok = False
        if credentials_exists:
            try:
                self.credentials()
                gmail_ok = bool(self.gmail_profile().get("emailAddress"))
                calendar_ok = isinstance(
                    self.calendar_list_events(
                        datetime.utcnow().isoformat() + "Z",
                        (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
                        max_results=1,
                    ),
                    list,
                )
                drive_ok = isinstance(self.drive_list_files(query="", page_size=1), list)
                tasks_ok = isinstance(self.tasks_list_tasklists(max_results=1), list)
            except Exception as exc:  # noqa: BLE001
                credentials_error = str(exc)
        return {
            "config_path": os.environ.get("GOOGLE_CONNECT_CONFIG_PATH", self.config_path),
            "runtime_root": os.environ.get("GOOGLE_CONNECT_RUNTIME_ROOT"),
            "credentials_path": str(cfg.google.credentials_path),
            "token_path": str(cfg.google.token_path),
            "credentials_exists": credentials_exists,
            "token_exists": token_exists,
            "credentials_error": credentials_error,
            "surfaces": {
                "gmail": {"ok": gmail_ok},
                "calendar": {"ok": calendar_ok},
                "drive": {"ok": drive_ok},
                "tasks": {"ok": tasks_ok},
            },
        }

    def gmail_list_threads(self, query: str, max_results: int) -> list[dict[str, Any]]:
        cfg = self.config()
        response = (
            self.service("gmail", "v1")
            .users()
            .threads()
            .list(userId=cfg.google.gmail_user_id, q=query, maxResults=max_results)
            .execute()
        )
        summaries: list[dict[str, Any]] = []
        for thread_stub in response.get("threads", []):
            thread_id = thread_stub.get("id")
            if not thread_id:
                continue
            normalized = normalize_gmail_thread(
                get_gmail_thread(self.service("gmail", "v1"), cfg.google.gmail_user_id, thread_id),
                include_html=False,
            )
            summaries.append(thread_summary_from_normalized(normalized))
        return summaries

    def gmail_get_thread(self, thread_id: str, include_html: bool = False) -> dict[str, Any]:
        cfg = self.config()
        return normalize_gmail_thread(
            get_gmail_thread(self.service("gmail", "v1"), cfg.google.gmail_user_id, thread_id),
            include_html=include_html,
        )

    def gmail_create_draft(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None,
        bcc: list[str] | None,
        confirmed: bool,
    ) -> dict[str, Any]:
        cfg = self.config()
        require_write_allowed(cfg, "gmail", "draft", cfg.google.gmail_user_id, confirmed, self.logger())

        message = EmailMessage()
        message["To"] = ", ".join(to)
        message["Subject"] = subject
        if cc:
            message["Cc"] = ", ".join(cc)
        if bcc:
            message["Bcc"] = ", ".join(bcc)
        message.set_content(body)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        created = (
            self.service("gmail", "v1")
            .users()
            .drafts()
            .create(userId=cfg.google.gmail_user_id, body={"message": {"raw": raw}})
            .execute()
        )
        return {"draft": created}

    def calendar_list_events(self, time_min: str, time_max: str, max_results: int, calendar_id: str | None = None) -> list[dict[str, Any]]:
        cfg = self.config()
        response = (
            self.service("calendar", "v3")
            .events()
            .list(
                calendarId=calendar_id or cfg.google.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
            )
            .execute()
        )
        return response.get("items", [])

    def calendar_create_event(
        self,
        summary: str,
        start: str,
        timezone_name: str,
        end: str | None,
        duration_minutes: int,
        description: str | None,
        location: str | None,
        confirmed: bool,
    ) -> dict[str, Any]:
        cfg = self.config()
        require_write_allowed(cfg, "calendar", "create", cfg.google.calendar_id, confirmed, self.logger())
        from google_connect.runners.calendar_writer import parse_local_datetime

        start_dt = parse_local_datetime(start, timezone_name)
        end_dt = parse_local_datetime(end, timezone_name) if end else start_dt + timedelta(minutes=duration_minutes)
        body = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone_name},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone_name},
        }
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location
        created = self.service("calendar", "v3").events().insert(calendarId=cfg.google.calendar_id, body=body).execute()
        document = calendar_event_to_document(created, cfg.google.calendar_id)
        return {"event": created, "ekg_sync": self.safe_ingest_document(document)}

    def calendar_update_event(
        self,
        event_id: str,
        summary: str | None,
        start: str | None,
        timezone_name: str,
        end: str | None,
        duration_minutes: int | None,
        description: str | None,
        location: str | None,
        confirmed: bool,
    ) -> dict[str, Any]:
        cfg = self.config()
        require_write_allowed(cfg, "calendar", "update", cfg.google.calendar_id, confirmed, self.logger())
        from google_connect.runners.calendar_writer import parse_local_datetime

        event = self.service("calendar", "v3").events().get(calendarId=cfg.google.calendar_id, eventId=event_id).execute()
        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location
        if start is not None:
            start_dt = parse_local_datetime(start, timezone_name)
            end_dt = parse_local_datetime(end, timezone_name) if end else start_dt + timedelta(minutes=duration_minutes or 60)
            event["start"] = {"dateTime": start_dt.isoformat(), "timeZone": timezone_name}
            event["end"] = {"dateTime": end_dt.isoformat(), "timeZone": timezone_name}
        updated = (
            self.service("calendar", "v3").events().update(calendarId=cfg.google.calendar_id, eventId=event_id, body=event).execute()
        )
        document = calendar_event_to_document(updated, cfg.google.calendar_id)
        return {"event": updated, "ekg_sync": self.safe_ingest_document(document)}

    def calendar_delete_event(self, event_id: str, confirmed: bool) -> dict[str, Any]:
        cfg = self.config()
        require_delete_allowed(cfg, "calendar", cfg.google.calendar_id, confirmed, self.logger())
        self.service("calendar", "v3").events().delete(calendarId=cfg.google.calendar_id, eventId=event_id).execute()
        return {"deleted": True, "event_id": event_id}

    def drive_list_files(self, query: str, page_size: int) -> list[dict[str, Any]]:
        response = (
            self.service("drive", "v3")
            .files()
            .list(q=query or "trashed = false", pageSize=page_size, fields="files(id,name,mimeType,modifiedTime,webViewLink)")
            .execute()
        )
        return response.get("files", [])

    def drive_get_document(self, file_id: str) -> dict[str, Any]:
        service = self.service("drive", "v3")
        metadata = service.files().get(fileId=file_id, fields="id,name,mimeType,modifiedTime,owners,webViewLink,parents").execute()
        text = extract_file_text(service, metadata)
        return {"file": metadata, "text": text}

    def sheets_get_range(self, range_name: str, spreadsheet_id: str | None = None) -> dict[str, Any]:
        cfg = self.config()
        sheet_id = spreadsheet_id or cfg.google.sheets.spreadsheet_id
        return self.service("sheets", "v4").spreadsheets().values().get(spreadsheetId=sheet_id, range=range_name).execute()

    def sheets_update_range(self, range_name: str, values: list[list[Any]], confirmed: bool, spreadsheet_id: str | None = None) -> dict[str, Any]:
        cfg = self.config()
        sheet_id = spreadsheet_id or cfg.google.sheets.spreadsheet_id
        require_write_allowed(cfg, "sheets", "update", sheet_id, confirmed, self.logger())
        self.service("sheets", "v4").spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        response = self.sheets_get_range(range_name, sheet_id)
        document = sheet_range_to_document(sheet_id, range_name, response.get("values", []), "update")
        return {"range": response, "ekg_sync": self.safe_ingest_document(document)}

    def sheets_append_row(self, range_name: str, values: list[str], confirmed: bool, spreadsheet_id: str | None = None) -> dict[str, Any]:
        cfg = self.config()
        sheet_id = spreadsheet_id or cfg.google.sheets.spreadsheet_id
        require_write_allowed(cfg, "sheets", "append", sheet_id, confirmed, self.logger())
        self.service("sheets", "v4").spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [values]},
        ).execute()
        response = self.sheets_get_range(range_name, sheet_id)
        document = sheet_range_to_document(sheet_id, range_name, response.get("values", []), "append")
        return {"range": response, "ekg_sync": self.safe_ingest_document(document)}

    def tasks_list_tasklists(self, max_results: int) -> list[dict[str, Any]]:
        return list_tasklists(self.service("tasks", "v1"), max_results)

    def tasks_list_tasks(self, tasklist_ref: str, max_results: int) -> list[dict[str, Any]]:
        tasklist = resolve_tasklist(self.service("tasks", "v1"), tasklist_ref, self.config().google.tasks.page_size)
        return list_tasks(self.service("tasks", "v1"), tasklist["id"], max_results)

    def tasks_create_task(
        self, tasklist_ref: str, title: str, notes: str | None, due: str | None, parent: str | None, confirmed: bool
    ) -> dict[str, Any]:
        cfg = self.config()
        require_write_allowed(cfg, "tasks", "create", tasklist_ref, confirmed, self.logger())
        service = self.service("tasks", "v1")
        tasklist = resolve_tasklist(service, tasklist_ref, cfg.google.tasks.page_size)
        payload = {"title": title}
        if notes is not None:
            payload["notes"] = notes
        if due is not None:
            payload["due"] = due
        insert_kwargs = {"tasklist": tasklist["id"], "body": payload}
        if parent is not None:
            insert_kwargs["parent"] = parent
        created = service.tasks().insert(**insert_kwargs).execute()
        task = service.tasks().get(tasklist=tasklist["id"], task=created["id"]).execute()
        document = task_to_document(task, tasklist)
        return {"task": task, "ekg_sync": self.safe_ingest_document(document)}

    def tasks_update_task(
        self,
        tasklist_ref: str,
        task_id: str,
        title: str | None,
        notes: str | None,
        due: str | None,
        parent: str | None,
        confirmed: bool,
    ) -> dict[str, Any]:
        cfg = self.config()
        require_write_allowed(cfg, "tasks", "update", tasklist_ref, confirmed, self.logger())
        service = self.service("tasks", "v1")
        tasklist = resolve_tasklist(service, tasklist_ref, cfg.google.tasks.page_size)
        patch_body = {}
        for field, value in [("title", title), ("notes", notes), ("due", due), ("parent", parent)]:
            if value is not None:
                patch_body[field] = value
        service.tasks().patch(tasklist=tasklist["id"], task=task_id, body=patch_body).execute()
        if parent is not None:
            service.tasks().move(tasklist=tasklist["id"], task=task_id, parent=parent).execute()
        task = service.tasks().get(tasklist=tasklist["id"], task=task_id).execute()
        document = task_to_document(task, tasklist)
        return {"task": task, "ekg_sync": self.safe_ingest_document(document)}

    def tasks_complete_task(self, tasklist_ref: str, task_id: str, confirmed: bool) -> dict[str, Any]:
        cfg = self.config()
        require_write_allowed(cfg, "tasks", "complete", tasklist_ref, confirmed, self.logger())
        service = self.service("tasks", "v1")
        tasklist = resolve_tasklist(service, tasklist_ref, cfg.google.tasks.page_size)
        completed = {
            "status": "completed",
            "completed": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        service.tasks().patch(tasklist=tasklist["id"], task=task_id, body=completed).execute()
        task = service.tasks().get(tasklist=tasklist["id"], task=task_id).execute()
        document = task_to_document(task, tasklist)
        return {"task": task, "ekg_sync": self.safe_ingest_document(document)}

    def keep_list_notes(self, page_size: int = 20) -> list[dict[str, Any]]:
        cfg = self.config()
        if not cfg.google.keep.enabled:
            raise PermissionError("Google Keep is disabled in config")
        response = self.service("keep", "v1").notes().list(pageSize=page_size).execute()
        return response.get("notes", [])
