import asyncio

from utils.ai_adapter import get_adapter
from utils.overview_builder import OverviewBuild
from utils.overview_generator import OverviewGenerator
from utils.ai_output_sanitize import sanitize_ai_comment
from utils.preprocessor import TextCleaner, TokenManager
from utils.reporter import MarkdownReporter
from utils.terminal_ui import TerminalUI


class ScrapePipeline:
    """Coordinate crawling, deep enrichment, AI analysis, and report generation."""

    def __init__(self, deep_mode=False, limit=None, ai_mode=False):
        self.deep_mode = deep_mode
        self.limit_override = limit
        self.ai_mode = ai_mode
        self.ai_adapter = get_adapter() if ai_mode else None
        self.ui = TerminalUI()
        self.reporter = MarkdownReporter()
        self.overview_builder = OverviewBuild()
        self.overview_generator = OverviewGenerator()
        self.all_results = {}
        self.semaphore = asyncio.Semaphore(3)

    def run_task(self, name, spider_instance, default_limit=5):
        """Run one scraping task and optionally enrich items with deep content."""
        limit = self.limit_override if self.limit_override is not None else default_limit
        source_name = getattr(spider_instance, "source_name", "unknown")

        self.ui.print_task_header(name, self.deep_mode, self.ai_mode)

        task_results = []
        try:
            data = spider_instance.fetch_trending(limit=limit)
            if not data:
                self.ui.print_warning(f"{name}: no data found.")
                return

            for i, item in enumerate(data, 1):
                self.ui.print_progress(i, len(data), item.get("name", "Unknown"), status="Fetching")
                if self.deep_mode:
                    self._enrich_item_with_detail(spider_instance, item)
                item["_source_name"] = source_name
                task_results.append(item)

            if name in self.all_results:
                self.all_results[name].extend(task_results)
            else:
                self.all_results[name] = task_results
        except Exception as e:
            self.ui.print_error(f"{name} failed: {str(e)}")

    def _enrich_item_with_detail(self, spider_instance, item):
        """Fetch detail for one item and merge it into the list result."""
        fetch_detail = getattr(spider_instance, "fetch_detail", None)
        if not callable(fetch_detail):
            return

        detail_id = self._resolve_detail_identifier(item)
        if not detail_id:
            return

        try:
            detail = fetch_detail(detail_id)
        except Exception as e:
            self.ui.print_warning(f"{item.get('name', detail_id)} detail fetch failed: {str(e)}")
            return

        self._merge_detail_into_item(item, detail)

    def _resolve_detail_identifier(self, item):
        """Pick the best identifier key expected by spider.fetch_detail()."""
        for key in ("path", "slug", "item_id", "id", "name"):
            value = item.get(key)
            if value:
                return value
        return None

    def _merge_detail_into_item(self, item, detail):
        """Normalize deep detail payload into the list item shape."""
        if not isinstance(detail, dict):
            return

        raw_content = (
            detail.get("raw_content")
            or detail.get("raw_readme")
            or detail.get("readme")
            or detail.get("description")
            or ""
        )
        if raw_content:
            item["raw_content"] = raw_content

        if not item.get("desc") and detail.get("description"):
            item["desc"] = detail["description"]

        if not item.get("url"):
            item["url"] = detail.get("html_url") or detail.get("url") or item.get("url")

    async def process_ai_all(self):
        """Run AI analysis for all collected items."""
        if not self.ai_mode or not self.ai_adapter:
            return

        all_item_names = []
        for items in self.all_results.values():
            for item in items:
                all_item_names.append(item["name"])

        if not all_item_names:
            return

        self.ui.start_live_ai(all_item_names)

        tasks = []
        for items in self.all_results.values():
            for item in items:
                source_name = item.get("_source_name", "unknown")
                tasks.append(self._handle_deep_analysis_async(item, source_name))

        try:
            if tasks:
                await asyncio.gather(*tasks)

            failed_items_with_source = []
            for items in self.all_results.values():
                for item in items:
                    if item.get("ai_comment") and "鉂" in item["ai_comment"]:
                        source_name = item.get("_source_name", "unknown")
                        failed_items_with_source.append((item, source_name))

            if failed_items_with_source:
                self.ui.print_warning(
                    f"\nDetected {len(failed_items_with_source)} failed AI analyses, retrying in 15 seconds..."
                )
                await asyncio.sleep(15)

                retry_tasks = []
                for item, source_name in failed_items_with_source:
                    item["ai_comment"] = None
                    self.ui.update_ai_status(item["name"], "Retrying")
                    retry_tasks.append(self._handle_deep_analysis_async(item, source_name))

                if retry_tasks:
                    await asyncio.gather(*retry_tasks)
        finally:
            self.ui.stop_live_ai()

    async def _handle_deep_analysis_async(self, item, source_name):
        """Analyze one item with AI, preferring deep content when available."""
        content = item.get("raw_content", "") or item.get("description", "") or item.get("desc", "")
        if not content or not self.ai_adapter:
            return

        async with self.semaphore:
            self.ui.update_ai_status(item["name"], "Analyzing")

            clean_content = TextCleaner.clean_full(content)
            ai_input = TokenManager.smart_truncate(clean_content, max_chars=3000)

            def stream_callback(chunk):
                self.ui.update_ai_status(item["name"], "Analyzing", chunk=chunk)

            ai_comment = await self.ai_adapter.analyze_async(
                source=source_name,
                name=item["name"],
                content=ai_input,
                chunk_callback=stream_callback,
            )

            item["ai_comment"] = sanitize_ai_comment(ai_comment)
            if ai_comment and not self.ui.has_ai_preview(item["name"]):
                self.ui.set_ai_comment(item["name"], ai_comment, status="Done")
            else:
                self.ui.update_ai_status(item["name"], "Done")

            await asyncio.sleep(5)

    async def save_report(self):
        """Generate final reports from aggregated results."""
        if not self.all_results:
            return None

        report_data = self._convert_to_source_name_format()
        overview_payload = self.overview_builder.generate(report_data)
        overview_text = await self.overview_generator.generate(overview_payload)
        return self.reporter.generate_reports(
            report_data,
            overview_text=overview_text,
            source_summaries=overview_payload["source_summaries"],
        )

    def get_summary_data(self):
        """Return summary data grouped by source_name."""
        return self._convert_to_source_name_format()

    def _convert_to_source_name_format(self):
        """Convert task-name keyed results into source-name keyed results."""
        report_data = {}
        for items in self.all_results.values():
            for item in items:
                source_name = item.get("_source_name", "unknown")
                if source_name not in report_data:
                    report_data[source_name] = []
                item_copy = {k: v for k, v in item.items() if k != "_source_name"}
                report_data[source_name].append(item_copy)
        return report_data
