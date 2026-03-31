"""
Terminal UI presentation layer module
Provides high-performance multi-line parallel display and streaming comments using the rich library
"""

from typing import Optional, Dict, List
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


class TerminalUI:
    """Terminal UI renderer, optimized for parallel display using rich."""

    def __init__(self):
        self.console = Console()
        self.live: Optional[Live] = None
        self.status_map: Dict[str, str] = {}
        self.comment_map: Dict[str, str] = {}
        self.active_items: List[str] = []

    def print_task_header(self, name: str, deep_mode: bool, ai_mode: bool):
        """Print task launch header."""
        modes = []
        if deep_mode:
            modes.append("Deep")
        if ai_mode:
            modes.append("AI")
        mode_str = f" [[bold blue]{'+'.join(modes)}[/]]" if modes else ""
        self.console.print(f"\nStarting data source [bold green]{name}[/]{mode_str}")

    def print_progress(self, current: int, total: int, item_name: str, status: str = "Processing"):
        """Traditional single-line progress print, used for scraping phase."""
        percent = (current / total) * 100
        self.console.print(
            f"  Progress: [[cyan]{current}/{total}[/]] {percent:3.0f}% | {status}: {item_name[:30]}...",
            end='\r'
        )
        if current == total:
            self.console.print()

    def print_ai_thinking(self, name: str):
        """Compatibility preserved interface."""
        pass

    def _ai_status_columns(self, table: Table) -> None:
        """Shared column definitions with _generate_ai_table (ensures static header aligns with Live data area)."""
        table.add_column("Project Name", style="cyan", width=25, no_wrap=True)
        table.add_column("Status", style="yellow", width=15)
        table.add_column("AI Comment Preview", style="white")

    def _generate_ai_table(self) -> Table:
        """Generate table containing only data rows for Live (header is printed once outside Live to avoid repeated stacking in Windows terminal)."""
        table = Table(box=None, show_header=False, expand=True)
        self._ai_status_columns(table)

        for name in self.active_items:
            status = self.status_map.get(name, "Waiting...")
            comment = self.comment_map.get(name, "") or ""
            preview = comment.replace('\n', ' ').strip()
            if len(preview) > 60:
                preview = preview[:57] + "..."

            table.add_row(name, status, preview)
        return table

    def start_live_ai(self, item_names: List[str]):
        """Start Live display mode."""
        self.active_items = item_names
        for name in item_names:
            self.status_map[name] = "Preparing..."
            self.comment_map[name] = ""

        # Title and column names are rendered once outside Live; Live only refreshes data area to avoid header stacking on refresh.
        header = Table(
            title="Concurrent AI Deep Analysis Status",
            box=None,
            show_header=True,
            expand=True,
        )
        self._ai_status_columns(header)
        self.console.print(header)

        self.live = Live(
            console=self.console,
            auto_refresh=False,
            get_renderable=self._generate_ai_table,
        )
        self.live.start(refresh=True)

    def update_ai_status(self, name: str, status: str, chunk: Optional[str] = None):
        """Update AI status and comment content for a specific item."""
        if name in self.status_map:
            self.status_map[name] = status
            if chunk:
                self.comment_map[name] += chunk

            # Refresh immediately after receiving status or chunk to avoid streaming content not displaying in short responses
            if self.live:
                self.live.refresh()

    def has_ai_preview(self, name: str) -> bool:
        """Check if the current item already has visible AI preview content."""
        return bool((self.comment_map.get(name) or "").strip())

    def set_ai_comment(self, name: str, comment: str, status: Optional[str] = None):
        """Backfill final result when streaming preview is unavailable."""
        if name in self.comment_map:
            self.comment_map[name] = comment or ""
        if status and name in self.status_map:
            self.status_map[name] = status

        if self.live:
            self.live.refresh()

    def stop_live_ai(self):
        """Stop Live display mode."""
        if self.live:
            self.live.stop()
            self.live = None
        self.console.print("\nAI analysis phase complete.\n")

    def print_ai_comment(self, name: str, comment: str):
        """After AI analysis completes, print the complete formatted comment."""
        panel = Panel(
            Text(comment.strip(), style="white"),
            title=f"[bold cyan]{name}[/] AI Deep Analysis",
            border_style="blue",
            padding=(1, 2)
        )
        self.console.print(panel)

    def print_collection_summary(self, all_results: dict):
        """Print statistical summary table."""
        table = Table(title="System Operation Statistics Summary", show_header=True, header_style="bold magenta")
        table.add_column("Data Source", style="dim", width=25)
        table.add_column("Total Scraped", justify="right")
        table.add_column("AI Analysis Count", justify="right")

        total_items = 0
        total_ai = 0

        for source, items in all_results.items():
            count = len(items)
            ai_count = sum(1 for item in items if item.get('ai_comment'))
            table.add_row(source, str(count), str(ai_count))
            total_items += count
            total_ai += ai_count

        table.add_section()
        table.add_row("Total", str(total_items), str(total_ai), style="bold green")
        self.console.print("\n", table)

    def print_error(self, msg: str):
        self.console.print(f"\n[bold red]Error:[/] {msg}")

    def print_warning(self, msg: str):
        self.console.print(f"\n[bold yellow]Warning:[/] {msg}")

    def print_system_footer(self, report_result: Optional[dict] = None):
        self.console.print("\n[bold green]All tasks complete.[/]")
        if report_result:
            batch_dir = report_result.get('batch_dir')
            files = report_result.get('files', {})
            if batch_dir:
                self.console.print(f"Report batch directory: [link=file://{batch_dir}]{batch_dir}[/]")
            for label in ('overview', 'github', 'hf', 'ph'):
                file_path = files.get(label)
                if file_path:
                    self.console.print(f"  - {label}: [link=file://{file_path}]{file_path}[/]")
        self.console.print("=" * 60 + "\n")
