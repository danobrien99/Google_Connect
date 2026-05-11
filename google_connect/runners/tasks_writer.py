from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

from google_connect.runner_utils import ingest_document
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.runners.tasks_reader import list_tasklists
from google_connect.transformers import task_to_document
from google_connect.write_guards import require_write_allowed


def resolve_tasklist(service: Any, tasklist_ref: str, page_size: int) -> dict[str, Any]:
    for tasklist in list_tasklists(service, page_size):
        if tasklist.get("id") == tasklist_ref or tasklist.get("title") == tasklist_ref:
            return tasklist
    raise ValueError(f"unknown tasklist: {tasklist_ref}")


def refresh_task_document(service: Any, ekg: Any, extraction_mode: str, tasklist: dict[str, Any], task_id: str) -> dict[str, Any]:
    task = service.tasks().get(tasklist=tasklist["id"], task=task_id).execute()
    document = task_to_document(task, tasklist)
    ingest_result = ingest_document(ekg, document, extraction_mode)
    return {"task": task, "document_id": document["document_id"], "ingest_result": ingest_result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--tasklist", required=False)
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--notes")
    create_parser.add_argument("--due")
    create_parser.add_argument("--parent")
    create_parser.add_argument("--confirm-write", action="store_true")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--tasklist", required=False)
    update_parser.add_argument("--task-id", required=True)
    update_parser.add_argument("--title")
    update_parser.add_argument("--notes")
    update_parser.add_argument("--due")
    update_parser.add_argument("--parent")
    update_parser.add_argument("--confirm-write", action="store_true")

    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--tasklist", required=False)
    complete_parser.add_argument("--task-id", required=True)
    complete_parser.add_argument("--confirm-write", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config, ekg, _state, logger = bootstrap(args.config, "tasks_writer")
    if not config.google.tasks.enabled:
        runner_summary("tasks_writer", {"ok": False, "error": "tasks disabled"}, logger)
        raise SystemExit(1)

    service = google_service(config, "tasks", "v1")
    tasklist_ref = args.tasklist or config.google.tasks.default_tasklist
    if not tasklist_ref:
        raise ValueError("tasklist must be provided either via --tasklist or default_tasklist config")
    tasklist = resolve_tasklist(service, tasklist_ref, config.google.tasks.page_size)

    if args.command == "create":
        require_write_allowed(config, "tasks", "create", tasklist_ref, args.confirm_write, logger)
        payload = {"title": args.title}
        if args.notes is not None:
            payload["notes"] = args.notes
        if args.due is not None:
            payload["due"] = args.due
        insert_kwargs = {"tasklist": tasklist["id"], "body": payload}
        if args.parent is not None:
            insert_kwargs["parent"] = args.parent
        created = service.tasks().insert(**insert_kwargs).execute()
        refreshed = refresh_task_document(service, ekg, config.runtime.extraction_mode, tasklist, created["id"])
        runner_summary("tasks_writer", {"ok": True, "action": "create", "task_id": created["id"], **refreshed}, logger)
        return

    if args.command == "update":
        require_write_allowed(config, "tasks", "update", tasklist_ref, args.confirm_write, logger)
        patch_body = {}
        for field in ["title", "notes", "due", "parent"]:
            value = getattr(args, field)
            if value is not None:
                patch_body[field] = value
        service.tasks().patch(tasklist=tasklist["id"], task=args.task_id, body=patch_body).execute()
        if args.parent is not None:
            service.tasks().move(tasklist=tasklist["id"], task=args.task_id, parent=args.parent).execute()
        refreshed = refresh_task_document(service, ekg, config.runtime.extraction_mode, tasklist, args.task_id)
        runner_summary("tasks_writer", {"ok": True, "action": "update", "task_id": args.task_id, **refreshed}, logger)
        return

    require_write_allowed(config, "tasks", "complete", tasklist_ref, args.confirm_write, logger)
    completed = {
        "status": "completed",
        "completed": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    service.tasks().patch(tasklist=tasklist["id"], task=args.task_id, body=completed).execute()
    refreshed = refresh_task_document(service, ekg, config.runtime.extraction_mode, tasklist, args.task_id)
    runner_summary("tasks_writer", {"ok": True, "action": "complete", "task_id": args.task_id, **refreshed}, logger)


if __name__ == "__main__":
    main()
