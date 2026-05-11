from __future__ import annotations

import unittest

from google_connect.runners.calendar_writer import parse_local_datetime
from google_connect.runners.calendar_writer import build_parser as build_calendar_parser
from google_connect.runners.sheets_writer import build_parser as build_sheets_parser


class WriterTests(unittest.TestCase):
    def test_calendar_datetime_parser_applies_timezone(self) -> None:
        value = parse_local_datetime("2026-04-20T17:00", "Europe/Berlin")
        self.assertEqual(value.tzinfo.key, "Europe/Berlin")
        self.assertEqual(value.hour, 17)

    def test_sheets_append_parser_collects_values(self) -> None:
        parser = build_sheets_parser()
        args = parser.parse_args(
            [
                "--config",
                "config/google_connect.yaml",
                "append",
                "--range",
                "Contacts!A:B",
                "--value",
                "Alice",
                "--value",
                "alice@example.com",
            ]
        )
        self.assertEqual(args.values, ["Alice", "alice@example.com"])

    def test_calendar_delete_requires_confirmation_flag(self) -> None:
        parser = build_calendar_parser()
        args = parser.parse_args(
            [
                "--config",
                "config/google_connect.yaml",
                "delete",
                "--event-id",
                "event-1",
            ]
        )
        self.assertFalse(args.confirm_delete)
