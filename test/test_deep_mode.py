import unittest
from unittest.mock import patch

from core.pipeline import ScrapePipeline
from spiders.github_spider import GitHubSpider


class FakeAdapter:
    def __init__(self):
        self.calls = []

    async def analyze_async(self, source, name, content, chunk_callback):
        self.calls.append({"source": source, "name": name, "content": content})
        return f"analysis for {name}"


class StreamingFakeAdapter(FakeAdapter):
    async def analyze_async(self, source, name, content, chunk_callback):
        self.calls.append({"source": source, "name": name, "content": content})
        chunk_callback("streamed ")
        chunk_callback(f"analysis for {name}")
        return f"streamed analysis for {name}"


class SpySpider:
    source_name = "github"

    def __init__(self):
        self.fetch_detail_calls = []

    def fetch_trending(self, limit=5):
        return [
            {
                "name": "owner/repo",
                "path": "owner/repo",
                "desc": "short description",
                "url": "https://github.com/owner/repo",
            }
        ]

    def fetch_detail(self, repo_path):
        self.fetch_detail_calls.append(repo_path)
        return {
            "raw_content": "README deep content",
            "description": "long description",
        }


class ScrapePipelineDeepModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_deep_mode_fetches_detail_and_uses_raw_content_for_ai(self):
        fake_adapter = FakeAdapter()
        spider = SpySpider()

        with patch("core.pipeline.get_adapter", return_value=fake_adapter), patch(
            "core.pipeline.asyncio.sleep", return_value=None
        ):
            pipeline = ScrapePipeline(deep_mode=True, ai_mode=True)
            pipeline.run_task("GitHub Trending", spider, default_limit=1)
            await pipeline.process_ai_all()

        self.assertEqual(spider.fetch_detail_calls, ["owner/repo"])
        self.assertEqual(fake_adapter.calls[0]["content"], "README deep content")
        self.assertEqual(
            pipeline.all_results["GitHub Trending"][0]["raw_content"],
            "README deep content",
        )

    async def test_non_deep_mode_skips_detail_fetch(self):
        fake_adapter = FakeAdapter()
        spider = SpySpider()

        with patch("core.pipeline.get_adapter", return_value=fake_adapter), patch(
            "core.pipeline.asyncio.sleep", return_value=None
        ):
            pipeline = ScrapePipeline(deep_mode=False, ai_mode=True)
            pipeline.run_task("GitHub Trending", spider, default_limit=1)
            await pipeline.process_ai_all()

        self.assertEqual(spider.fetch_detail_calls, [])
        self.assertEqual(fake_adapter.calls[0]["content"], "short description")

    async def test_final_result_backfills_preview_only_when_stream_preview_is_empty(self):
        fake_adapter = FakeAdapter()
        spider = SpySpider()

        with patch("core.pipeline.get_adapter", return_value=fake_adapter), patch(
            "core.pipeline.asyncio.sleep", return_value=None
        ):
            pipeline = ScrapePipeline(deep_mode=False, ai_mode=True)
            pipeline.run_task("GitHub Trending", spider, default_limit=1)
            await pipeline.process_ai_all()

        self.assertEqual(pipeline.ui.comment_map["owner/repo"], "analysis for owner/repo")

    async def test_stream_preview_is_preserved_when_chunks_arrive(self):
        fake_adapter = StreamingFakeAdapter()
        spider = SpySpider()

        with patch("core.pipeline.get_adapter", return_value=fake_adapter), patch(
            "core.pipeline.asyncio.sleep", return_value=None
        ):
            pipeline = ScrapePipeline(deep_mode=False, ai_mode=True)
            pipeline.run_task("GitHub Trending", spider, default_limit=1)
            await pipeline.process_ai_all()

        self.assertEqual(
            pipeline.ui.comment_map["owner/repo"],
            "streamed analysis for owner/repo",
        )


class GitHubSpiderDetailTests(unittest.TestCase):
    def test_fetch_detail_maps_readme_to_raw_content(self):
        spider = GitHubSpider()

        with patch.object(
            spider,
            "_get_details",
            return_value={
                "full_name": "owner/repo",
                "description": "repo description",
                "html_url": "https://github.com/owner/repo",
            },
        ), patch.object(spider, "fetch_readme", return_value="README body"):
            detail = spider.fetch_detail("owner/repo")

        assert detail is not None
        self.assertEqual(detail["raw_content"], "README body")
        self.assertEqual(detail["raw_readme"], "README body")
        self.assertEqual(detail["full_name"], "owner/repo")


if __name__ == "__main__":
    unittest.main()
