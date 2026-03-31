import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spiders.producthunt_spider import ProductHuntSpider


class ProductHuntSpiderTests(unittest.TestCase):
    @patch("spiders.producthunt_spider.Config.REQUEST_TIMEOUT", 30)
    @patch("spiders.producthunt_spider.Config.PH_API_TOKEN", "valid-token")
    def test_fetch_trending_requires_posts_edges(self):
        body = {
            "data": {
                "posts": {
                    "edges": [
                        {
                            "node": {
                                "name": "App",
                                "tagline": "TL",
                                "description": "Long desc",
                                "votesCount": 99,
                                "url": "https://ph.dev/p/app",
                                "slug": "app",
                            }
                        }
                    ]
                }
            }
        }
        resp = MagicMock()
        resp.json = lambda: body
        resp.raise_for_status = lambda: None

        with patch("spiders.producthunt_spider.requests.post", return_value=resp):
            spider = ProductHuntSpider()
            out = spider.fetch_trending(limit=1)

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["name"], "App")
        self.assertEqual(out[0]["slug"], "app")
        self.assertIn("Votes: 99", out[0]["stats"])

    @patch("spiders.producthunt_spider.Config.REQUEST_TIMEOUT", 30)
    @patch("spiders.producthunt_spider.Config.PH_API_TOKEN", "")
    def test_fetch_trending_raises_without_token(self):
        spider = ProductHuntSpider()
        with self.assertRaises(ValueError):
            spider.fetch_trending(limit=1)

    @patch("spiders.producthunt_spider.Config.REQUEST_TIMEOUT", 30)
    @patch("spiders.producthunt_spider.Config.PH_API_TOKEN", "t")
    def test_fetch_detail_builds_raw_content(self):
        body = {
            "data": {
                "post": {
                    "name": "P",
                    "tagline": "Tag",
                    "description": "Body text",
                    "votesCount": 1,
                    "url": "u",
                    "reviewsCount": 0,
                }
            }
        }
        resp = MagicMock()
        resp.json = lambda: body
        resp.raise_for_status = lambda: None
        with patch("spiders.producthunt_spider.requests.post", return_value=resp):
            spider = ProductHuntSpider()
            detail = spider.fetch_detail("my-slug")
        self.assertIsNotNone(detail)
        self.assertIn("Tag", detail["raw_content"])
        self.assertIn("Body text", detail["raw_content"])


if __name__ == "__main__":
    unittest.main()
