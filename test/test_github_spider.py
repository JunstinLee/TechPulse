import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spiders.github_spider import GitHubSpider


_TRENDING_HTML = """
<article class="Box-row">
<a href="/owner/hub-repo" data-view-component="true" class="Link">repo</a>
850 stars today
</article>
"""


class GitHubSpiderTests(unittest.TestCase):
    @patch("spiders.github_spider.Config.REQUEST_TIMEOUT", 30)
    @patch("spiders.github_spider.Config.GITHUB_TOKEN", "")
    def test_fetch_trending_parses_page_and_enriches_via_api(self):
        api_payload = {
            "full_name": "owner/hub-repo",
            "description": "A test repo",
            "stargazers_count": 1200,
            "forks_count": 40,
            "language": "Python",
            "html_url": "https://github.com/owner/hub-repo",
        }

        page_resp = MagicMock()
        page_resp.text = _TRENDING_HTML
        page_resp.raise_for_status = lambda: None

        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.json = lambda: api_payload

        with patch("spiders.github_spider.requests.get", side_effect=[page_resp, api_resp]) as rg:
            spider = GitHubSpider(since="daily")
            out = spider.fetch_trending(limit=1)

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["name"], "owner/hub-repo")
        self.assertIn("Growth today: 850", out[0]["stats"])
        self.assertEqual(rg.call_count, 2)

    @patch("spiders.github_spider.Config.REQUEST_TIMEOUT", 30)
    @patch("spiders.github_spider.Config.GITHUB_TOKEN", "")
    def test_fetch_readme_decodes_base64(self):
        readme_resp = MagicMock()
        readme_resp.status_code = 200
        readme_resp.json = lambda: {"content": "SGkK"}  # "Hi\n" in base64

        with patch("spiders.github_spider.requests.get", return_value=readme_resp):
            spider = GitHubSpider()
            text = spider.fetch_readme("owner/repo")

        self.assertIn("Hi", text)


if __name__ == "__main__":
    unittest.main()
