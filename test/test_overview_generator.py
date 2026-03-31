"""OverviewGenerator 异步 generate 的分支测试。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.overview_generator import OverviewGenerator


class OverviewGeneratorAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_fallback_when_overview_disabled(self):
        gen = OverviewGenerator()
        payload = {"fallback_text": "FB", "prompt_context": "{}"}
        with patch("utils.overview_generator.Config.OVERVIEW_ENABLED", False):
            out = await gen.generate(payload)
        self.assertEqual(out, "FB")

    async def test_returns_fallback_when_ai_disabled(self):
        gen = OverviewGenerator()
        payload = {"fallback_text": "Fallback overview.", "prompt_context": "{}"}
        with patch("utils.overview_generator.Config.OVERVIEW_ENABLED", True), patch(
            "utils.overview_generator.Config.OVERVIEW_AI_ENABLED", False
        ):
            out = await gen.generate(payload)
        self.assertEqual(out, "Fallback overview.")

    async def test_returns_fallback_when_api_key_missing(self):
        gen = OverviewGenerator()
        payload = {"fallback_text": "FB", "prompt_context": "ctx"}
        with patch("utils.overview_generator.Config.OVERVIEW_ENABLED", True), patch(
            "utils.overview_generator.Config.OVERVIEW_AI_ENABLED", True
        ), patch("utils.overview_generator.Config.OPENROUTER_API_KEY", ""):
            out = await gen.generate(payload)
        self.assertEqual(out, "FB")

    async def test_returns_fallback_when_prompt_context_empty(self):
        gen = OverviewGenerator()
        payload = {"fallback_text": "FB", "prompt_context": ""}
        with patch("utils.overview_generator.Config.OVERVIEW_ENABLED", True), patch(
            "utils.overview_generator.Config.OVERVIEW_AI_ENABLED", True
        ), patch("utils.overview_generator.Config.OPENROUTER_API_KEY", "sk-test"):
            out = await gen.generate(payload)
        self.assertEqual(out, "FB")

    async def test_returns_fallback_when_prompt_loader_raises(self):
        gen = OverviewGenerator()
        gen.prompt_loader = MagicMock()
        gen.prompt_loader.load.side_effect = FileNotFoundError("no template")
        payload = {"fallback_text": "FB", "prompt_context": "ctx"}
        with patch("utils.overview_generator.Config.OVERVIEW_ENABLED", True), patch(
            "utils.overview_generator.Config.OVERVIEW_AI_ENABLED", True
        ), patch("utils.overview_generator.Config.OPENROUTER_API_KEY", "sk-test"):
            out = await gen.generate(payload)
        self.assertEqual(out, "FB")

    async def test_uses_complete_async_and_respects_empty_response(self):
        gen = OverviewGenerator()
        gen.prompt_loader = MagicMock()
        gen.prompt_loader.load.return_value = "system prompt text"
        gen.ai_adapter = MagicMock()
        gen.ai_adapter.complete_async = AsyncMock(return_value="")
        payload = {"fallback_text": "FB", "prompt_context": "ctx"}
        with patch("utils.overview_generator.Config.OVERVIEW_ENABLED", True), patch(
            "utils.overview_generator.Config.OVERVIEW_AI_ENABLED", True
        ), patch("utils.overview_generator.Config.OPENROUTER_API_KEY", "sk-test"), patch(
            "utils.overview_generator.Config.OVERVIEW_MODEL", "m"
        ), patch("utils.overview_generator.Config.OVERVIEW_MAX_OUTPUT_CHARS", 100):
            out = await gen.generate(payload)
        self.assertEqual(out, "FB")
        gen.ai_adapter.complete_async.assert_awaited_once()

    async def test_returns_model_text_when_complete_succeeds(self):
        gen = OverviewGenerator()
        gen.prompt_loader = MagicMock()
        gen.prompt_loader.load.return_value = "system"
        gen.ai_adapter = MagicMock()
        gen.ai_adapter.complete_async = AsyncMock(return_value="  Hello overview  ")
        payload = {"fallback_text": "FB", "prompt_context": "ctx"}
        with patch("utils.overview_generator.Config.OVERVIEW_ENABLED", True), patch(
            "utils.overview_generator.Config.OVERVIEW_AI_ENABLED", True
        ), patch("utils.overview_generator.Config.OPENROUTER_API_KEY", "sk-test"), patch(
            "utils.overview_generator.Config.OVERVIEW_MODEL", "m"
        ), patch("utils.overview_generator.Config.OVERVIEW_MAX_OUTPUT_CHARS", 50):
            out = await gen.generate(payload)
        self.assertEqual(out, "Hello overview")


if __name__ == "__main__":
    unittest.main()
