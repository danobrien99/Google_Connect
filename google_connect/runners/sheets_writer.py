from __future__ import annotations

import argparse
import json

from google_connect.runner_utils import ingest_document
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.transformers import sheet_range_to_document
from google_connect.write_guards import require_write_allowed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--range", required=True)
    update_parser.add_argument("--values-json", required=True, help='JSON 2D array, e.g. [["A","B"],["C","D"]]')
    update_parser.add_argument("--value-input-option", default="USER_ENTERED")
    update_parser.add_argument("--confirm-write", action="store_true")

    append_parser = subparsers.add_parser("append")
    append_parser.add_argument("--range", required=True)
    append_parser.add_argument("--value", action="append", required=True, dest="values")
    append_parser.add_argument("--value-input-option", default="USER_ENTERED")
    append_parser.add_argument("--insert-data-option", default="INSERT_ROWS")
    append_parser.add_argument("--confirm-write", action="store_true")
    return parser


def refresh_range_document(service, ekg, extraction_mode: str, spreadsheet_id: str, range_name: str, operation: str) -> dict:
    response = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = response.get("values", [])
    document = sheet_range_to_document(spreadsheet_id, range_name, values, operation)
    ingest_result = ingest_document(ekg, document, extraction_mode)
    return {"document_id": document["document_id"], "ingest_result": ingest_result, "values": values}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config, ekg, _state, logger = bootstrap(args.config, "sheets_writer")
    service = google_service(config, "sheets", "v4")
    spreadsheet_id = config.google.sheets.spreadsheet_id

    if args.command == "update":
        require_write_allowed(config, "sheets", "update", spreadsheet_id, args.confirm_write, logger)
        values = json.loads(args.values_json)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=args.range,
            valueInputOption=args.value_input_option,
            body={"values": values},
        ).execute()
        refreshed = refresh_range_document(service, ekg, config.runtime.extraction_mode, spreadsheet_id, args.range, "update")
        runner_summary("sheets_writer", {"ok": True, "action": "update", "range": args.range, **refreshed}, logger)
        return

    require_write_allowed(config, "sheets", "append", spreadsheet_id, args.confirm_write, logger)
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=args.range,
        valueInputOption=args.value_input_option,
        insertDataOption=args.insert_data_option,
        body={"values": [args.values]},
    ).execute()
    refreshed = refresh_range_document(service, ekg, config.runtime.extraction_mode, spreadsheet_id, args.range, "append")
    runner_summary("sheets_writer", {"ok": True, "action": "append", "range": args.range, **refreshed}, logger)


if __name__ == "__main__":
    main()
