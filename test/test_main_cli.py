import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _spider(source: str):
    m = MagicMock()
    m.fetch_trending.return_value = []
    m.source_name = source
    return m


class MainCliTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_deep_and_no_ai_passed_to_pipeline(self):
        captured = {}

        class DummyPipeline:
            def __init__(self, deep_mode=False, limit=None, ai_mode=False):
                captured.update(deep_mode=deep_mode, limit=limit, ai_mode=ai_mode)

            def run_task(self, *a, **k):
                pass

            async def process_ai_all(self):
                pass

            async def save_report(self):
                return None

            def get_summary_data(self):
                return {}

        class DummyUI:
            def print_collection_summary(self, *a, **k):
                pass

            def print_system_footer(self, *a, **k):
                pass

        with patch.object(sys, "argv", ["main.py", "--no-deep", "--no-ai"]), patch(
            "main.ScrapePipeline", DummyPipeline
        ), patch("main.TerminalUI", lambda: DummyUI()), patch(
            "main.GitHubSpider", lambda *a, **k: _spider("github")
        ), patch("main.HuggingFaceSpider", lambda *a, **k: _spider("hf")), patch(
            "main.ProductHuntSpider", lambda *a, **k: _spider("ph")
        ), patch("main.notifier.is_enabled", return_value=False):
            from main import main_async

            await main_async()

        self.assertFalse(captured["deep_mode"])
        self.assertFalse(captured["ai_mode"])


if __name__ == "__main__":
    unittest.main()
