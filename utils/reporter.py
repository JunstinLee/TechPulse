import os
import logging
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from utils.ai_output_sanitize import strip_think_tags

# Get logger
logger = logging.getLogger("MarkdownReporter")


class MarkdownReporter:
    """Markdown report generator class."""

    def __init__(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_dir = os.path.join(self.current_dir, 'templates')
        self.output_dir = os.path.join(os.path.dirname(self.current_dir), 'reports')

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        self.overview_template_name = 'overview.md.j2'
        self.source_template_name = 'source_detail.md.j2'
        self.source_titles = {
            'github': 'GitHub Trending',
            'hf': 'Hugging Face Trending',
            'ph': 'Product Hunt Hot'
        }

    def generate_reports(self, data: dict, overview_text: str = "", source_summaries: list = None):
        """Generate overview and per-source Markdown reports based on the input data dictionary."""
        try:
            batch_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            batch_dir = os.path.join(self.output_dir, f'TECH_PULSE_{batch_id}')
            os.makedirs(batch_dir, exist_ok=True)

            source_summaries = source_summaries or self._build_source_summaries(data)
            files = {}

            overview_template = self.env.get_template(self.overview_template_name)
            overview_context = {
                'date': generated_at,
                'total_count': sum(summary['count'] for summary in source_summaries),
                'source_summaries': source_summaries,
                'overview_text': overview_text,
            }
            overview_content = self._sanitize_content(overview_template.render(overview_context))
            files['overview'] = self._write_file(batch_dir, 'overview.md', overview_content)

            source_template = self.env.get_template(self.source_template_name)
            for source_key in ('github', 'hf', 'ph'):
                items = data.get(source_key, [])
                source_context = {
                    'date': generated_at,
                    'source_key': source_key,
                    'source_title': self.source_titles.get(source_key, source_key.upper()),
                    'items': items,
                    'count': len(items)
                }
                source_content = self._sanitize_content(source_template.render(source_context))
                files[source_key] = self._write_file(batch_dir, f'{source_key}.md', source_content)

            logger.info(f"Reports successfully generated: {batch_dir}")
            return {
                'batch_dir': batch_dir,
                'files': files
            }
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            return None

    def _build_source_summaries(self, data: dict):
        """Construct statistics and lightweight project list needed for the overview template."""
        summaries = []
        for source_key in ('github', 'hf', 'ph'):
            items = data.get(source_key, [])
            summaries.append({
                'key': source_key,
                'title': self.source_titles.get(source_key, source_key.upper()),
                'count': len(items),
                'ai_count': sum(1 for item in items if item.get('ai_comment')),
                'file_name': f'{source_key}.md',
                'entries': items
            })
        return summaries

    def _sanitize_content(self, content: str) -> str:
        """Remove model thinking chains and other content that should not be written to the final report."""
        return strip_think_tags(content)

    def _write_file(self, directory: str, filename: str, content: str) -> str:
        """Write rendered content to a Markdown file and return the path."""
        file_path = os.path.join(directory, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path
