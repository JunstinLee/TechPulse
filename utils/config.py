import os

from dotenv import load_dotenv


load_dotenv()


def _get_bool_env(name: str, default: str = "false") -> bool:
    """Parse a boolean environment variable with a safe default."""
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Centralized application configuration."""

    PH_API_TOKEN = os.getenv("PH_API_TOKEN", "YOUR_PH_API_TOKEN_HERE")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    HF_TOKEN = os.getenv("HF_TOKEN", "")

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.5:free")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    CACHE_DIR = os.getenv("CACHE_DIR", "data/cache")

    GITHUB_API_URL = "https://api.github.com"
    HF_API_URL = "https://huggingface.co/api"
    PH_API_URL = "https://api.producthunt.com/v2/api/graphql"

    REQUEST_TIMEOUT = 120
    MAX_RETRIES = 3
    MIN_REQUEST_INTERVAL = float(os.getenv("MIN_REQUEST_INTERVAL", "5"))
    OPENROUTER_REQUESTS_PER_MINUTE = int(os.getenv("OPENROUTER_REQUESTS_PER_MINUTE", "20"))
    OPENROUTER_429_COOLDOWN_SECONDS = float(os.getenv("OPENROUTER_429_COOLDOWN_SECONDS", "30"))

    MAX_CONTENT_LENGTH = 3000

    # Channel AI comment: maximum characters before writing to report (0 means no truncation)
    AI_COMMENT_MAX_CHARS = int(os.getenv("AI_COMMENT_MAX_CHARS", "2000"))
    # Streaming only accumulates delta.content; if the entire segment is empty, fallback to reasoning field (some gateways only write body to reasoning)
    OPENROUTER_STREAM_FALLBACK_TO_REASONING = _get_bool_env(
        "OPENROUTER_STREAM_FALLBACK_TO_REASONING", "false"
    )
    # Limit max_tokens for channel analysis requests, aligned with short comment prompts, to reduce verbose output
    AI_COMMENT_MAX_TOKENS = int(os.getenv("AI_COMMENT_MAX_TOKENS", "768"))
    # Optional: extra fields merged into chat/completions JSON (JSON object string, empty by default means not merged)
    OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON = os.getenv(
        "OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON", ""
    ).strip()

    OVERVIEW_ENABLED = _get_bool_env("OVERVIEW_ENABLED", "true")
    OVERVIEW_AI_ENABLED = _get_bool_env("OVERVIEW_AI_ENABLED", "true")
    OVERVIEW_MODEL = os.getenv("OVERVIEW_MODEL", OPENROUTER_MODEL)
    OVERVIEW_MAX_INPUT_ITEMS = int(os.getenv("OVERVIEW_MAX_INPUT_ITEMS", "6"))
    OVERVIEW_MAX_OUTPUT_CHARS = int(os.getenv("OVERVIEW_MAX_OUTPUT_CHARS", "1200"))
    OVERVIEW_INCLUDE_AI_COMMENT = _get_bool_env("OVERVIEW_INCLUDE_AI_COMMENT", "true")

    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
    TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")
    REPORT_WATCH_DIR = os.getenv("REPORT_WATCH_DIR", "reports")
    TG_PUSH_STATE_FILE = os.getenv("TG_PUSH_STATE_FILE", "data/cache/telegram_push_state.json")
