import sys
import unittest
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.reporter import MarkdownReporter


class MarkdownReporterExtraTests(unittest.TestCase):
    def test_build_source_summaries_counts_ai_comments(self):
        rep = MarkdownReporter()
        data = {
            "github": [{"name": "a", "ai_comment": "x"}, {"name": "b"}],
            "hf": [],
            "ph": [],
        }
        sums = rep._build_source_summaries(data)
        self.assertEqual(sums[0]["ai_count"], 1)
        self.assertEqual(sums[0]["count"], 2)

    def test_sanitize_content_strips_think(self):
        rep = MarkdownReporter()
        ref_line = (_ROOT / "test" / "test_ai_reasoning_handling.py").read_text(encoding="utf-8").splitlines()[31]
        q = '"'
        sample = ref_line[ref_line.index(q) + 1 : ref_line.rindex(q)]
        raw = rep._sanitize_content(sample)
        self.assertNotIn("hidden", raw)
        self.assertIn("Hello", raw)


if __name__ == "__main__":
    unittest.main()
