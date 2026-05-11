from __future__ import annotations

from types import SimpleNamespace
import unittest

from google_connect.write_guards import require_delete_allowed, require_write_allowed


class _Logger:
    def info(self, *args, **kwargs) -> None:
        return None


class GuardrailTests(unittest.TestCase):
    def _config(self):
        return SimpleNamespace(
            write_guards=SimpleNamespace(
                enable_writes=True,
                gmail_draft_enabled=True,
                calendar_write_enabled=True,
                calendar_delete_enabled=False,
                sheets_write_enabled=True,
                tasks_write_enabled=True,
                writable_tasklists=["My Tasks"],
                writable_calendars=["primary"],
                writable_spreadsheets=["sheet-1"],
            )
        )

    def test_tasks_require_allowlisted_target(self) -> None:
        with self.assertRaises(PermissionError):
            require_write_allowed(self._config(), "tasks", "create", "Other", True, _Logger())

    def test_calendar_delete_requires_dedicated_toggle(self) -> None:
        with self.assertRaises(PermissionError):
            require_delete_allowed(self._config(), "calendar", "primary", True, _Logger())

    def test_gmail_send_is_rejected_even_when_writes_are_enabled(self) -> None:
        with self.assertRaises(PermissionError):
            require_write_allowed(self._config(), "gmail", "send", "me", True, _Logger())

    def test_gmail_draft_requires_dedicated_toggle(self) -> None:
        config = self._config()
        config.write_guards.gmail_draft_enabled = False
        with self.assertRaises(PermissionError):
            require_write_allowed(config, "gmail", "draft", "me", True, _Logger())
