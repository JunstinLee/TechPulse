import requests

from utils.config import Config


class HuggingFaceSpider:
    """Hugging Face trending crawler."""

    source_name = "hf"

    def __init__(self, category="models"):
        self.category = category
        self.base_url = f"https://huggingface.co/api/{self.category}"
        self.token = Config.HF_TOKEN
        self.timeout = Config.REQUEST_TIMEOUT

    def fetch_detail(self, item_id):
        """Fetch model or space detail and normalize readme into raw_content."""
        try:
            url = f"{self.base_url}/{item_id}"
            headers = {"User-Agent": "TechDistill-Bot"}
            if self.token and self.token.strip():
                headers["Authorization"] = f"Bearer {self.token}"

            resp = requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                data["raw_content"] = data.get("modelCard") or data.get("readme", "") or data.get("description", "")
                return data
        except Exception as e:
            print(f"HF detail fetch failed ({item_id}): {e}")
        return None

    def fetch_trending(self, limit=5):
        """Fetch trending Hugging Face items."""
        print(f"Fetching Hugging Face {self.category.upper()} trending list...")

        params = {"trending": True, "limit": limit, "full": True}
        headers = {"User-Agent": "Mozilla/5.0"}

        if self.token and self.token != "YOUR_HF_TOKEN_HERE" and self.token.strip() != "":
            headers["Authorization"] = f"Bearer {self.token}"

        resp = requests.get(self.base_url, params=params, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data:
            item_id = item.get("id")
            results.append(
                {
                    "name": item_id,
                    "item_id": item_id,
                    "desc": f"Author: {item.get('author')}",
                    "stats": f"Likes: {item.get('likes', 0):,}",
                    "url": f"https://huggingface.co/{item_id}",
                    "raw_content": item.get("modelCard") or item.get("readme", ""),
                }
            )
        return results
