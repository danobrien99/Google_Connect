from __future__ import annotations

import argparse
from typing import Any

from google_connect.runner_utils import ingest_document, parse_rfc3339
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.transformers import task_to_document


def list_tasklists(service: Any, page_size: int) -> list[dict[str, Any]]:
    tasklists: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = service.tasklists().list(maxResults=page_size, pageToken=page_token).execute()
        tasklists.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return tasklists


def filter_tasklists(tasklists: list[dict[str, Any]], allowed: list[str]) -> list[dict[str, Any]]:
    if not allowed:
        return tasklists
    allowed_set = set(allowed)
    return [tasklist for tasklist in tasklists if tasklist.get("id") in allowed_set or tasklist.get("title") in allowed_set]


def list_tasks(service: Any, tasklist_id: str, page_size: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = (
            service.tasks()
            .list(tasklist=tasklist_id, maxResults=page_size, pageToken=page_token, showCompleted=False, showHidden=False)
            .execute()
        )
        tasks.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return tasks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, "tasks_reader")
    if not config.google.tasks.enabled:
        runner_summary("tasks_reader", {"ok": True, "skipped": True, "reason": "tasks disabled"}, logger)
        return

    service = google_service(config, "tasks", "v1")
    previous_high_water_mark = (state.load("tasks_reader_cursor", {}) or {}).get("updated")
    tasklists = filter_tasklists(list_tasklists(service, config.google.tasks.page_size), config.google.tasks.tasklist_filter)

    fetched_count = 0
    ingested_count = 0
    failures: list[dict[str, str]] = []
    high_water_mark = previous_high_water_mark

    for tasklist in tasklists:
        tasks = list_tasks(service, tasklist["id"], config.google.tasks.page_size)
        filtered_tasks = []
        for task in tasks:
            updated = task.get("updated")
            if previous_high_water_mark and updated and parse_rfc3339(updated) <= parse_rfc3339(previous_high_water_mark):
                continue
            filtered_tasks.append(task)
        fetched_count += len(filtered_tasks)
        for task in sorted(filtered_tasks, key=lambda item: parse_rfc3339(item.get("updated")).timestamp()):
            try:
                document = task_to_document(task, tasklist)
                ingest_document(ekg, document, config.runtime.extraction_mode)
                ingested_count += 1
                high_water_mark = task.get("updated", high_water_mark)
            except Exception as exc:  # noqa: BLE001
                failures.append({"id": str(task.get("id", "unknown")), "error": str(exc)})
                logger.exception("tasks_reader failure task_id=%s", task.get("id"))
                break
        if failures:
            break

    summary = {
        "ok": not failures,
        "fetched_count": fetched_count,
        "ingested_count": ingested_count,
        "failed_count": len(failures),
        "next_cursor": previous_high_water_mark if failures else high_water_mark,
        "partial_failure": bool(failures),
        "failures": failures,
    }
    state.save("tasks_reader_cursor", {"updated": summary["next_cursor"]})
    runner_summary("tasks_reader", summary, logger)


if __name__ == "__main__":
    main()
