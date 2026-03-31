"""流式 delta 抽取与 ai_comment 清洗的单元测试。"""

import unittest

from utils.ai_adapter import _extract_delta_reasoning_only, _extract_stream_text_from_delta
from utils.ai_output_sanitize import sanitize_ai_comment, strip_think_tags


class StreamDeltaExtractTests(unittest.TestCase):
    def test_content_only_default(self):
        d = {"reasoning_content": "think", "content": "ans"}
        self.assertEqual(_extract_stream_text_from_delta(d), "ans")

    def test_content_only_ignores_reasoning(self):
        d = {"reasoning_content": "long think", "content": ""}
        self.assertEqual(_extract_stream_text_from_delta(d), "")

    def test_include_reasoning_concat(self):
        d = {"reasoning_content": "A", "reasoning": "", "content": "B"}
        self.assertEqual(
            _extract_stream_text_from_delta(d, include_reasoning=True),
            "AB",
        )

    def test_reasoning_only_helper(self):
        d = {"reasoning_content": "x", "reasoning": "y", "content": "z"}
        self.assertEqual(_extract_delta_reasoning_only(d), "xy")


class SanitizeTests(unittest.TestCase):
    def test_strip_think_tags(self):
        raw = "Hello <think>hidden</think> world"
        self.assertEqual(strip_think_tags(raw).strip(), "Hello  world")

    def test_sanitize_truncates(self):
        long_text = "x" * 100
        out = sanitize_ai_comment(long_text, max_chars=50)
        self.assertTrue(out.endswith("..."))
        self.assertEqual(len(out), 50 + 3)


if __name__ == "__main__":
    unittest.main()
