import argparse
import asyncio
import logging
import sys
import os

from core.pipeline import ScrapePipeline
from spiders.github_spider import GitHubSpider
from spiders.huggingface_spider import HuggingFaceSpider
from spiders.producthunt_spider import ProductHuntSpider
from utils.telegram_notifier import notifier
from utils.terminal_ui import TerminalUI


def configure_logging():
    # Set default level to WARNING to prevent INFO logs from libraries like httpx from interfering with rich.live rendering
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Ensure specific modules remain silent
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def main_async():
    """Main async entrypoint for the Prism pipeline."""
    parser = argparse.ArgumentParser(description="TechDistill pipeline")
    parser.add_argument("--deep", action="store_true", default=True, help="Enable deep scraping")
    parser.add_argument("--no-deep", action="store_false", dest="deep")
    parser.add_argument("--ai", action="store_true", default=True, help="Enable AI analysis")
    parser.add_argument("--no-ai", action="store_false", dest="ai")
    parser.add_argument("--limit", type=int, default=None, help="Override fetch limit for all sources")
    parser.add_argument(
        "--watch",
        action="store_true",
        default=True,
        help="Enable Telegram push after report generation",
    )
    parser.add_argument("--no-watch", action="store_false", dest="watch")
    args = parser.parse_args()

    configure_logging()

    print("TechDistill pipeline")

    tasks = [
        ("GitHub Trending", GitHubSpider(since="daily"), 25),
        ("Hugging Face Models", HuggingFaceSpider(category="models"), 5),
        ("Product Hunt Today", ProductHuntSpider(), 10),
    ]

    pipeline = ScrapePipeline(deep_mode=args.deep, limit=args.limit, ai_mode=args.ai)
    ui = TerminalUI()

    for name, spider, limit in tasks:
        pipeline.run_task(name, spider, default_limit=limit)

    await pipeline.process_ai_all()

    ui.print_collection_summary(pipeline.get_summary_data())
    report_result = await pipeline.save_report()

    if args.watch and report_result:
        if notifier.is_enabled():
            files = report_result.get("files", {})
            ui.console.print("\n[bold cyan]Pushing reports to Telegram...[/]")
            for label, file_path in files.items():
                if file_path:
                    status = notifier.push_report(file_path)
                    filename = os.path.basename(file_path)
                    if status == "sent":
                        ui.console.print(f"  - [green]Sent:[/] {filename}")
                    elif status == "skipped":
                        ui.console.print(f"  - [yellow]Skipped:[/] {filename} (no changes)")
                    elif status == "failed":
                        ui.console.print(f"  - [red]Failed:[/] {filename}")
        else:
            logging.getLogger("main").warning(
                "Telegram push is enabled but TG_BOT_TOKEN or TG_CHAT_ID is missing."
            )

    ui.print_system_footer(report_result)


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nUser interrupted the program.")
        sys.exit(0)
