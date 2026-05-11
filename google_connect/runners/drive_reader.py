from __future__ import annotations

import argparse
from typing import Any

from google_connect.runner_utils import ingest_document, parse_rfc3339
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.transformers import drive_file_to_document, extract_drive_text

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
EXPORT_MIME_TYPE = "text/plain"
SUPPORTED_BLOB_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def build_drive_query(config: Any, high_water_mark: str | None) -> str:
    clauses = ["trashed = false"]
    if config.google.drive.query:
        clauses.append(f"({config.google.drive.query})")
    if config.google.drive.folder_ids:
        folder_query = " or ".join(f"'{folder_id}' in parents" for folder_id in config.google.drive.folder_ids)
        clauses.append(f"({folder_query})")
    if high_water_mark:
        clauses.append(f"modifiedTime > '{high_water_mark}'")
    if config.google.drive.include_mime_types:
        mime_query = " or ".join(f"mimeType = '{mime}'" for mime in config.google.drive.include_mime_types)
        clauses.append(f"({mime_query})")
    return " and ".join(clauses)


def list_drive_files(service: Any, query: str, page_size: int) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=query,
                pageSize=page_size,
                pageToken=page_token,
                orderBy="modifiedTime",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, owners, webViewLink, parents)",
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def extract_file_text(service: Any, file_metadata: dict[str, Any]) -> str:
    mime_type = file_metadata.get("mimeType")
    if mime_type == GOOGLE_DOC_MIME:
        content = service.files().export_media(fileId=file_metadata["id"], mimeType=EXPORT_MIME_TYPE).execute()
        return content.decode("utf-8", errors="replace")
    if mime_type in SUPPORTED_BLOB_MIME_TYPES:
        content = service.files().get_media(fileId=file_metadata["id"]).execute()
        return extract_drive_text(mime_type, content)
    raise ValueError(f"unsupported drive file mime type: {mime_type}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, "drive_reader")
    if not config.google.drive.enabled:
        runner_summary("drive_reader", {"ok": True, "skipped": True, "reason": "drive disabled"}, logger)
        return

    service = google_service(config, "drive", "v3")
    previous_high_water_mark = (state.load("drive_reader_cursor", {}) or {}).get("modified_time")
    files = list_drive_files(service, build_drive_query(config, previous_high_water_mark), config.google.drive.page_size)
    ordered_files = sorted(files, key=lambda item: parse_rfc3339(item.get("modifiedTime")).timestamp())

    failures: list[dict[str, str]] = []
    ingested_count = 0
    high_water_mark = previous_high_water_mark
    for file_metadata in ordered_files:
        try:
            text = extract_file_text(service, file_metadata)
            document = drive_file_to_document(file_metadata, text)
            ingest_document(ekg, document, config.runtime.extraction_mode)
            ingested_count += 1
            high_water_mark = file_metadata.get("modifiedTime", high_water_mark)
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": str(file_metadata.get("id", "unknown")), "error": str(exc)})
            logger.exception("drive_reader failure file_id=%s", file_metadata.get("id"))
            break

    summary = {
        "ok": not failures,
        "fetched_count": len(ordered_files),
        "ingested_count": ingested_count,
        "failed_count": len(failures),
        "next_cursor": previous_high_water_mark if failures else high_water_mark,
        "partial_failure": bool(failures),
        "failures": failures,
    }
    state.save("drive_reader_cursor", {"modified_time": summary["next_cursor"]})
    runner_summary("drive_reader", summary, logger)


if __name__ == "__main__":
    main()
