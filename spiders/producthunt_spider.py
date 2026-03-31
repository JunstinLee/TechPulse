import requests

from utils.config import Config


class ProductHuntSpider:
    """Product Hunt trending crawler."""

    source_name = "ph"

    def __init__(self):
        self.url = Config.PH_API_URL
        self.token = Config.PH_API_TOKEN
        self.timeout = Config.REQUEST_TIMEOUT

    def fetch_detail(self, slug):
        """Fetch product detail and normalize available text fields into raw_content."""
        print(f"Fetching Product Hunt detail: {slug}...")

        query = """
        query($slug: String!) {
          post(slug: $slug) {
            name
            tagline
            description
            votesCount
            url
            reviewsCount
          }
        }
        """

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        variables = {"slug": slug}

        try:
            resp = requests.post(
                self.url,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                print(f"PH API error: {data['errors'][0]['message']}")
                return None

            post = data["data"]["post"]
            post["raw_content"] = "\n\n".join(
                part for part in [post.get("tagline", ""), post.get("description", "")] if part
            )
            return post
        except Exception as e:
            print(f"PH detail fetch failed ({slug}): {e}")
        return None

    def fetch_trending(self, limit=5):
        """Fetch today's Product Hunt trending list."""
        print("Fetching Product Hunt trending list...")

        if not self.token or self.token == "YOUR_PH_API_TOKEN_HERE" or self.token.strip() == "":
            raise ValueError("Missing valid PH_API_TOKEN")

        query = """
        {
          posts(first: %d, order: VOTES) {
            edges {
              node {
                name
                tagline
                description
                votesCount
                url
                slug
              }
            }
          }
        }
        """ % limit

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        resp = requests.post(self.url, json={"query": query}, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            raise Exception(data["errors"][0]["message"])

        posts = data["data"]["posts"]["edges"]
        results = []
        for edge in posts:
            node = edge["node"]
            results.append(
                {
                    "name": node["name"],
                    "desc": node["tagline"],
                    "stats": f"Votes: {node['votesCount']:,}",
                    "url": node["url"],
                    "slug": node.get("slug"),
                    "raw_content": node.get("description", ""),
                }
            )
        return results
