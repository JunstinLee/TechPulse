import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.preprocessor import ContentExtractor, TextCleaner, TokenManager


class TextCleanerTests(unittest.TestCase):
    def test_remove_images_markdown_and_html(self):
        raw = "a ![x](y) b <img src=z> c"
        self.assertEqual(TextCleaner.remove_images(raw), "a  b  c")

    def test_empty_string_returns_empty(self):
        self.assertEqual(TextCleaner.remove_images(""), "")
        self.assertEqual(TextCleaner.clean_full(""), "")

    def test_remove_badges(self):
        raw = "x [![a](b)](c) y ![](https://img.shields.io/foo) z"
        out = TextCleaner.remove_badges(raw)
        self.assertNotIn("shields.io", out)
        self.assertNotIn("[![", out)

    def test_remove_toc_lines(self):
        raw = "# Table of Contents\n\n- [a](#a)\n\nbody"
        out = TextCleaner.remove_toc(raw)
        self.assertIn("body", out)
        self.assertNotIn("# Table", out)

    def test_clean_full_collapses_blank_lines(self):
        raw = "a\n\n\n\nb"
        self.assertEqual(TextCleaner.clean_full(raw), "a\n\nb")


class ContentExtractorTests(unittest.TestCase):
    def test_short_text_passthrough(self):
        t = "hello"
        self.assertEqual(ContentExtractor.extract_core_sections(t), "hello")

    def test_long_text_returns_full_when_no_core_sections_recognized(self):
        text = "x" * 2000
        self.assertEqual(ContentExtractor.extract_core_sections(text), text)


class TokenManagerTests(unittest.TestCase):
    def test_no_truncate_when_under_limit(self):
        self.assertEqual(TokenManager.smart_truncate("abc", max_chars=10), "abc")

    def test_brutal_truncate_when_no_core_fit(self):
        long_line = "z" * 5000
        out = TokenManager.smart_truncate(long_line, max_chars=100)
        self.assertTrue(out.startswith("z" * 100))
        self.assertIn("[...内容已截断...]", out)


if __name__ == "__main__":
    unittest.main()
