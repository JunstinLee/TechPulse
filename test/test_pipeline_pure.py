import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.pipeline import ScrapePipeline


class ResolveDetailIdentifierTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = ScrapePipeline(deep_mode=False, ai_mode=False)

    def test_prefers_path_over_name(self):
        item = {"path": "a/b", "name": "n"}
        self.assertEqual(self.pipeline._resolve_detail_identifier(item), "a/b")

    def test_slug_when_no_path(self):
        item = {"slug": "my-slug", "name": "n"}
        self.assertEqual(self.pipeline._resolve_detail_identifier(item), "my-slug")

    def test_name_fallback(self):
        item = {"name": "only-name"}
        self.assertEqual(self.pipeline._resolve_detail_identifier(item), "only-name")

    def test_empty_returns_none(self):
        self.assertIsNone(self.pipeline._resolve_detail_identifier({}))


class MergeDetailTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = ScrapePipeline(deep_mode=False, ai_mode=False)

    def test_non_dict_noop(self):
        item = {"name": "x"}
        self.pipeline._merge_detail_into_item(item, None)
        self.pipeline._merge_detail_into_item(item, "str")
        self.assertNotIn("raw_content", item)

    def test_raw_content_priority_chain(self):
        item = {"name": "x"}
        self.pipeline._merge_detail_into_item(
            item, {"raw_content": "RC", "description": "D", "html_url": "https://h"}
        )
        self.assertEqual(item["raw_content"], "RC")

    def test_raw_readme_when_no_raw_content(self):
        item = {}
        self.pipeline._merge_detail_into_item(item, {"raw_readme": "RR"})
        self.assertEqual(item["raw_content"], "RR")

    def test_fills_desc_and_url(self):
        item = {}
        self.pipeline._merge_detail_into_item(
            item, {"description": "long", "html_url": "https://example.com/repo"}
        )
        self.assertEqual(item["desc"], "long")
        self.assertEqual(item["url"], "https://example.com/repo")


class ConvertSourceNameTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = ScrapePipeline(deep_mode=False, ai_mode=False)

    def test_strips_source_key_and_groups_by_source_name(self):
        self.pipeline.all_results = {
            "TaskA": [
                {"name": "one", "_source_name": "github", "k": 1},
                {"name": "two", "_source_name": "github"},
            ],
            "TaskB": [{"name": "three", "_source_name": "hf"}],
        }
        out = self.pipeline._convert_to_source_name_format()
        self.assertEqual(len(out["github"]), 2)
        self.assertEqual(len(out["hf"]), 1)
        self.assertNotIn("_source_name", out["github"][0])
        self.assertEqual(out["github"][0]["name"], "one")

    def test_get_summary_data_matches_convert(self):
        self.pipeline.all_results = {
            "X": [{"name": "a", "_source_name": "ph"}],
        }
        self.assertEqual(self.pipeline.get_summary_data(), self.pipeline._convert_to_source_name_format())


if __name__ == "__main__":
    unittest.main()
