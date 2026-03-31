"""
Unified sanitization for model output: thinking chain tag removal and length cap.

Consistent with the regex historically used by MarkdownReporter to avoid drift in two places.
"""

import re
from typing import Optional

# Collapse 3 or more consecutive newlines into two, without altering single newline structure of bullets
_COLLAPSE_BLANK_LINES = re.compile(r"\n{3,}")

# Consistent with historical reporter implementation (tags used by DeepSeek / MiniMax, etc.)
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think_tags(text: str) -> str:
    """Remove thinking chain fragments wrapped in think tags."""
    if not text:
        return ""
    return _THINK_BLOCK.sub("", text)


def sanitize_ai_comment(text: Optional[str], max_chars: Optional[int] = None) -> str:
    """
    Before writing channel AI comments to the report: remove tags, strip, and truncate by character hard limit.

    max_chars defaults to Config.AI_COMMENT_MAX_CHARS; if 0, no truncation.
    """
    from utils.config import Config

    s = strip_think_tags(text or "")
    s = s.strip()
    s = _COLLAPSE_BLANK_LINES.sub("\n\n", s)
    limit = max_chars if max_chars is not None else Config.AI_COMMENT_MAX_CHARS
    if limit and len(s) > limit:
        s = s[:limit].rstrip() + "..."
    return s
