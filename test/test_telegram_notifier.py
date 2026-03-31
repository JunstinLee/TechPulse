import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.telegram_notifier import TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    def test_is_enabled_requires_token_and_chat(self):
        with patch("utils.telegram_notifier.Config.TG_BOT_TOKEN", ""), patch(
            "utils.telegram_notifier.Config.TG_CHAT_ID", "1"
        ):
            n = TelegramNotifier()
            self.assertFalse(n.is_enabled())
        with patch("utils.telegram_notifier.Config.TG_BOT_TOKEN", "t"), patch(
            "utils.telegram_notifier.Config.TG_CHAT_ID", ""
        ):
            n = TelegramNotifier()
            self.assertFalse(n.is_enabled())
        with patch("utils.telegram_notifier.Config.TG_BOT_TOKEN", "t"), patch(
            "utils.telegram_notifier.Config.TG_CHAT_ID", "c"
        ):
            n = TelegramNotifier()
            self.assertTrue(n.is_enabled())

    def test_has_changed_true_for_new_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("hello")
            path = f.name
        try:
            with tempfile.TemporaryDirectory() as td:
                state = Path(td) / "state.json"
                with patch("utils.telegram_notifier.Config.TG_BOT_TOKEN", "t"), patch(
                    "utils.telegram_notifier.Config.TG_CHAT_ID", "c"
                ), patch("utils.telegram_notifier.Config.TG_PUSH_STATE_FILE", str(state)):
                    n = TelegramNotifier()
                    self.assertTrue(n.has_changed(path))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_push_report_skips_when_unchanged(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("same")
            path = f.name
        try:
            with tempfile.TemporaryDirectory() as td:
                state = Path(td) / "state.json"
                with patch("utils.telegram_notifier.Config.TG_BOT_TOKEN", "t"), patch(
                    "utils.telegram_notifier.Config.TG_CHAT_ID", "c"
                ), patch("utils.telegram_notifier.Config.TG_PUSH_STATE_FILE", str(state)):
                    n = TelegramNotifier()
                    n.mark_as_pushed(path)
                    self.assertEqual(n.push_report(path), "skipped")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_push_report_sends_and_marks_state(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("new content v2")
            path = f.name
        try:
            with tempfile.TemporaryDirectory() as td:
                state = Path(td) / "state.json"
                with patch("utils.telegram_notifier.Config.TG_BOT_TOKEN", "tok"), patch(
                    "utils.telegram_notifier.Config.TG_CHAT_ID", "1"
                ), patch("utils.telegram_notifier.Config.TG_PUSH_STATE_FILE", str(state)), patch(
                    "utils.telegram_notifier.requests.post",
                    return_value=MagicMock(**{"raise_for_status": lambda: None, "json": lambda: {"ok": True}}),
                ):
                    n = TelegramNotifier()
                    status = n.push_report(path)
                    self.assertEqual(status, "sent")
                    data = json.loads(state.read_text(encoding="utf-8"))
                    self.assertEqual(len(data), 1)
                    self.assertEqual(len(next(iter(data.values()))), 32)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_push_report_disabled_when_not_configured(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            path = f.name
        try:
            with patch("utils.telegram_notifier.Config.TG_BOT_TOKEN", ""), patch(
                "utils.telegram_notifier.Config.TG_CHAT_ID", ""
            ):
                n = TelegramNotifier()
                self.assertEqual(n.push_report(path), "disabled")
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
