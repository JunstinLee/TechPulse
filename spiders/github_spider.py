import base64
import re

import requests

from utils.config import Config


class GitHubSpider:
    """GitHub Trending crawler."""

    source_name = "github"

    def __init__(self, since="daily", language=None):
        self.since = since
        self.language = language
        self.base_url = "https://github.com/trending"
        self.api_url = "https://api.github.com/repos"
        self.token = Config.GITHUB_TOKEN
        self.timeout = Config.REQUEST_TIMEOUT

    def fetch_detail(self, repo_path):
        """Fetch repository detail and normalize README into raw_content."""
        details = self._get_details(repo_path)
        if not details:
            return None

        readme_content = self.fetch_readme(repo_path)
        details["raw_readme"] = readme_content
        details["raw_content"] = readme_content or details.get("description", "")
        return details

    def fetch_readme(self, repo_path):
        """Fetch and decode README content from the GitHub API."""
        try:
            url = f"{self.api_url}/{repo_path}/readme"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "TechDistill-Bot",
            }
            if self.token and self.token.strip():
                headers["Authorization"] = f"token {self.token}"

            resp = requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                content_base64 = data.get("content", "")
                if content_base64:
                    decoded_bytes = base64.b64decode(content_base64)
                    return decoded_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"README fetch failed ({repo_path}): {e}")
        return ""

    def fetch_trending(self, limit=25):
        """Fetch the trending repository list and enrich with basic repository stats."""
        url = f"{self.base_url}/{self.language}" if self.language else self.base_url
        if self.since:
            url += f"?since={self.since}"

        print("Fetching project list from GitHub Trending page...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://github.com/",
        }
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()

        articles = re.findall(r'<article class="Box-row">.*?</article>', resp.text, re.DOTALL)

        raw_list = []
        for article in articles:
            path_match = re.search(
                r'href="(/([^/"]+/[^/"]+))" data-view-component="true" class="Link',
                article,
            )
            if not path_match:
                continue
            repo_path = path_match.group(1).strip("/")

            growth_match = re.search(r"([\d,]+)\s+stars\s+(today|this week|this month)", article)
            growth = growth_match.group(1).replace(",", "") if growth_match else "0"

            raw_list.append({"path": repo_path, "growth": growth})
            if len(raw_list) >= limit:
                break

        print(f"List parsing finished, enriching {len(raw_list)} repositories via API...")

        results = []
        since_text = {"daily": "today", "weekly": "this week", "monthly": "this month"}.get(
            self.since, "today"
        )

        for item in raw_list:
            details = self._get_details(item["path"])

            if details:
                results.append(
                    {
                        "name": details.get("full_name", item["path"]),
                        "path": item["path"],
                        "desc": details.get("description") or "No description",
                        "stats": (
                            f"Stars: {details.get('stargazers_count', 0):,} | "
                            f"Forks: {details.get('forks_count', 0):,} | "
                            f"Growth {since_text}: {int(item['growth']):,} | "
                            f"Language: {details.get('language') or 'Unknown'}"
                        ),
                        "url": details.get("html_url", f"https://github.com/{item['path']}"),
                    }
                )
            else:
                results.append(
                    {
                        "name": item["path"],
                        "path": item["path"],
                        "desc": "Repository details unavailable",
                        "stats": f"Growth {since_text}: {int(item['growth']):,}",
                        "url": f"https://github.com/{item['path']}",
                    }
                )
        return results

    def _get_details(self, repo_path):
        """Fetch repository detail from the GitHub API."""
        try:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Mozilla/5.0",
            }
            if self.token and self.token != "YOUR_GITHUB_TOKEN_HERE" and self.token.strip() != "":
                headers["Authorization"] = f"token {self.token}"

            resp = requests.get(f"{self.api_url}/{repo_path}", headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None
