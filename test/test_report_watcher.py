import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if "watchdog.observers" not in sys.modules:
    _wd = types.ModuleType("watchdog")
    _ob = types.ModuleType("watchdog.observers")
    _ob.Observer = MagicMock
    _ev = types.ModuleType("watchdog.events")

    class _StubHandler:
        pass

    _ev.FileSystemEventHandler = _StubHandler
    sys.modules["watchdog"] = _wd
    sys.modules["watchdog.observers"] = _ob
    sys.modules["watchdog.events"] = _ev

from utils.report_watcher import ReportFileHandler


class ReportFileHandlerTests(unittest.TestCase):
    def test_ignores_non_markdown(self):
        h = ReportFileHandler("/tmp")
        with patch("utils.report_watcher.notifier.push_report") as push:
            h._process_event("/tmp/readme.txt")
            push.assert_not_called()

    def test_ignores_md_without_overview_in_name(self):
        h = ReportFileHandler("/tmp")
        with patch("utils.report_watcher.notifier.push_report") as push:
            h._process_event("/tmp/github.md")
            push.assert_not_called()

    def test_processes_overview_md_when_stable(self):
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "overview.md")
            Path(fp).write_text("x", encoding="utf-8")
            h = ReportFileHandler(td)

            def fake_getsize(_):
                return 1

            with patch("utils.report_watcher.notifier.push_report") as push, patch(
                "utils.report_watcher.time.sleep"
            ), patch("utils.report_watcher.time.time", side_effect=[0, 0, 1]), patch(
                "utils.report_watcher.os.path.getsize", side_effect=fake_getsize
            ):
                h._process_event(fp)
            push.assert_called_once_with(fp)
            self.assertIn(fp, h.processed_files)

    def test_wait_until_stable_times_out(self):
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "overview.md")
            Path(fp).write_text("growing", encoding="utf-8")
            h = ReportFileHandler(td)
            with patch("utils.report_watcher.time.sleep"), patch(
                "utils.report_watcher.time.time",
                side_effect=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            ), patch("utils.report_watcher.os.path.getsize", side_effect=[1, 2, 3, 4]):
                self.assertFalse(h._wait_until_file_stable(fp, timeout=3))


if __name__ == "__main__":
    unittest.main()
