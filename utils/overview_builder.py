import json

from utils.config import Config


class OverviewBuild:
    """Build overview payload data for the overview generator."""

    def build(self, data: dict) -> dict:
        source_summaries = self._build_source_summaries(data)
        highlight_items = self._build_highlight_items(data)
        total_count = sum(summary["count"] for summary in source_summaries)

        return {
            "total_count": total_count,
            "source_summaries": source_summaries,
            "highlight_items": highlight_items,
            "fallback_text": self._build_fallback_text(total_count, source_summaries, highlight_items),
            "prompt_context": self._build_prompt_context(total_count, source_summaries, highlight_items),
        }

    def generate(self, data: dict) -> dict:
        """Backward-compatible alias used by pipeline.py."""
        return self.build(data)

    def _build_source_summaries(self, data: dict) -> list[dict]:
        source_titles = {
            "github": "GitHub Trending",
            "hf": "Hugging Face Trending",
            "ph": "Product Hunt Hot",
        }

        summaries = []
        for source_key in ("github", "hf", "ph"):
            items = data.get(source_key, [])
            summaries.append(
                {
                    "key": source_key,
                    "title": source_titles.get(source_key, source_key.upper()),
                    "count": len(items),
                    "ai_count": sum(1 for item in items if item.get("ai_comment")),
                    "file_name": f"{source_key}.md",
                    "entries": items,
                }
            )
        return summaries

    def _build_highlight_items(self, data: dict) -> list[dict]:
        limit = max(1, Config.OVERVIEW_MAX_INPUT_ITEMS)
        highlights = []

        for source_key in ("github", "hf", "ph"):
            for item in data.get(source_key, []):
                highlight = {
                    "source": source_key,
                    "name": item.get("name", ""),
                    "desc": item.get("desc", ""),
                    "stats": item.get("stats", ""),
                    "url": item.get("url", ""),
                }
                if Config.OVERVIEW_INCLUDE_AI_COMMENT and item.get("ai_comment"):
                    highlight["ai_comment"] = item["ai_comment"]
                highlights.append(highlight)
                if len(highlights) >= limit:
                    return highlights

        return highlights

    def _build_fallback_text(
        self, total_count: int, source_summaries: list[dict], highlight_items: list[dict]
    ) -> str:
        if total_count == 0:
            return "Today's scan did not collect any qualifying updates."

        active_sources = [summary for summary in source_summaries if summary["count"] > 0]
        source_text = ", ".join(
            f"{summary['title']} ({summary['count']})" for summary in active_sources
        ) or "the tracked sources"

        if not highlight_items:
            return f"Today's scan collected updates across {source_text}."

        highlight_names = ", ".join(
            item["name"] for item in highlight_items[: min(3, len(highlight_items))] if item["name"]
        )
        if highlight_names:
            return f"Today's scan collected updates across {source_text}. Standout projects include {highlight_names}."

        return f"Today's scan collected updates across {source_text}."

    def _build_prompt_context(
        self, total_count: int, source_summaries: list[dict], highlight_items: list[dict]
    ) -> str:
        payload = {
            "total_count": total_count,
            "source_summaries": [
                {
                    "key": summary["key"],
                    "title": summary["title"],
                    "count": summary["count"],
                    "ai_count": summary["ai_count"],
                }
                for summary in source_summaries
            ],
            "highlight_items": highlight_items,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


class OverviewBuilder(OverviewBuild):
    """Compatibility alias for tests and future clearer naming."""
