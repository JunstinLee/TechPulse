import os
import unittest
import shutil

from utils.overview_builder import OverviewBuilder
from utils.reporter import MarkdownReporter


class OverviewBuilderTests(unittest.TestCase):
    def test_build_creates_fallback_text_and_source_summaries(self):
        builder = OverviewBuilder()
        data = {
            "github": [
                {
                    "name": "owner/repo",
                    "desc": "Fast inference runtime for multimodal agents.",
                    "stats": "Stars: 12,300 | Forks: 900 | Growth today: 850 | Language: Python",
                    "url": "https://github.com/owner/repo",
                    "ai_comment": "Strong developer traction and clear deployment story.",
                }
            ],
            "hf": [
                {
                    "name": "org/model",
                    "desc": "Author: org",
                    "stats": "Likes: 420",
                    "url": "https://huggingface.co/org/model",
                }
            ],
            "ph": [],
        }

        payload = builder.build(data)

        self.assertEqual(payload["total_count"], 2)
        self.assertIn("Today's scan collected updates", payload["fallback_text"])
        self.assertEqual(payload["source_summaries"][0]["count"], 1)
        self.assertEqual(payload["highlight_items"][0]["name"], "owner/repo")


class MarkdownReporterOverviewTests(unittest.TestCase):
    def test_generate_reports_writes_overview_text(self):
        reporter = MarkdownReporter()
        tmpdir = os.path.join(os.getcwd(), "test_output_reports")
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.makedirs(tmpdir, exist_ok=True)
        try:
            reporter.output_dir = tmpdir

            result = reporter.generate_reports(
                {"github": [], "hf": [], "ph": []},
                overview_text="English natural language overview.",
                source_summaries=[
                    {"key": "github", "title": "GitHub Trending", "count": 0, "ai_count": 0, "file_name": "github.md"},
                    {"key": "hf", "title": "Hugging Face Trending", "count": 0, "ai_count": 0, "file_name": "hf.md"},
                    {"key": "ph", "title": "Product Hunt Hot", "count": 0, "ai_count": 0, "file_name": "ph.md"},
                ],
            )

            self.assertIsNotNone(result)
            assert result is not None  # 缩窄类型，供类型检查器识别（generate_reports 失败时返回 None）
            overview_path = result["files"]["overview"]
            self.assertTrue(os.path.exists(overview_path))

            with open(overview_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("## Overview", content)
            self.assertIn("English natural language overview.", content)
            self.assertIn("[GitHub Trending](github.md)", content)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
