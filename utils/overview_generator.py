import logging

from utils.ai_adapter import PromptLoader, get_adapter
from utils.ai_output_sanitize import strip_think_tags
from utils.config import Config


logger = logging.getLogger("OverviewGenerator")


class OverviewGenerator:
    """Generate the final overview text with graceful fallback."""

    def __init__(self):
        self.prompt_loader = PromptLoader()
        self.ai_adapter = get_adapter()

    async def generate(self, overview_payload: dict) -> str:
        fallback_text = overview_payload.get("fallback_text", "")

        if not Config.OVERVIEW_ENABLED:
            return fallback_text

        if not Config.OVERVIEW_AI_ENABLED:
            return fallback_text

        if not Config.OPENROUTER_API_KEY:
            logger.warning("Overview AI is enabled but OPENROUTER_API_KEY is missing. Falling back.")
            return fallback_text

        prompt_context = overview_payload.get("prompt_context", "")
        if not prompt_context:
            return fallback_text

        try:
            system_prompt = self.prompt_loader.load(
                "overview_editor",
                variables={"max_chars": Config.OVERVIEW_MAX_OUTPUT_CHARS},
            )
            response_text = await self._request_overview(system_prompt, prompt_context)
            return response_text or fallback_text
        except Exception as exc:
            logger.warning("Overview generation failed, using fallback: %s", exc)
            return fallback_text

    async def _request_overview(self, system_prompt: str, prompt_context: str) -> str:
        response_text = await self.ai_adapter.complete_async(
            system_prompt=system_prompt,
            user_content=prompt_context,
            model=Config.OVERVIEW_MODEL,
            max_tokens=min(2048, max(300, Config.OVERVIEW_MAX_OUTPUT_CHARS)),
            temperature=0.4,
        )
        content = strip_think_tags(response_text.strip())
        return content[: Config.OVERVIEW_MAX_OUTPUT_CHARS].strip()
