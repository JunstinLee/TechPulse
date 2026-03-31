"""
AI Adapter Module
Provides prompt loading, AI invocation, and caching functionality
"""

import os
import time
import hashlib
import json
import requests
import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable

try:
    from diskcache import Cache
except ImportError:
    class Cache(dict):
        """Fallback in-memory cache used when diskcache is unavailable."""

        def __init__(self, directory=None):
            super().__init__()

        def clear(self):
            super().clear()

        def iterkeys(self):
            return iter(self.keys())

from utils.config import Config
from utils.openrouter_rate_limiter import get_openrouter_rate_limiter

# Get logger
logger = logging.getLogger("AIAdapter")
_adapter_instance = None

class PromptLoader:
    """Prompt loader - loads prompts from Markdown files and injects variables"""
    
    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Initialize prompt loader
        
        Args:
            prompts_dir: Prompt template directory, defaults to utils/prompts
        """
        if prompts_dir is None:
            # Get absolute path of utils/prompts directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            prompts_dir = os.path.join(os.path.dirname(current_dir), 'utils', 'prompts')
        self.prompts_dir = prompts_dir
    
    def load(self, template_name: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """
        Load prompt template and replace variables
        """
        template_path = os.path.join(self.prompts_dir, f"{template_name}.md")
        
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Prompt template not found: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace variables
        if variables:
            for key, value in variables.items():
                placeholder = f"{{{{{key}}}}}"
                content = content.replace(placeholder, str(value))
        
        return content


def generate_content_hash(content: str) -> str:
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def _extract_stream_text_from_delta(delta: Dict[str, Any], *, include_reasoning: bool = False) -> str:
    """
    Extract text from delta of streaming chunks.

    - include_reasoning=False (default): Only content field, do not concatenate API's segmented reasoning into the report.
    - include_reasoning=True: Consistent with historical behavior, concatenate reasoning_content, reasoning, content (used for benchmark scripts, etc.).
    """
    if not isinstance(delta, dict):
        return ""
    if include_reasoning:
        parts: List[str] = []
        for key in ("reasoning_content", "reasoning", "content"):
            piece = delta.get(key)
            if isinstance(piece, str) and piece:
                parts.append(piece)
        return "".join(parts)
    piece = delta.get("content")
    return piece if isinstance(piece, str) else ""


def _extract_delta_reasoning_only(delta: Dict[str, Any]) -> str:
    """Only concatenate reasoning-related fields (used as fallback when stream ends and content is empty)."""
    if not isinstance(delta, dict):
        return ""
    parts: List[str] = []
    for key in ("reasoning_content", "reasoning"):
        piece = delta.get(key)
        if isinstance(piece, str) and piece:
            parts.append(piece)
    return "".join(parts)


def generate_cache_key(source: str, name: str, content: str, model: str = "") -> str:
    """Cache key must include model, otherwise changing models will incorrectly hit old results and streaming preview degrades to one-time backfill."""
    content_hash = generate_content_hash(content)
    return f"{source}:{name}:{content_hash}:{model}"


class OpenRouterAdapter:
    """OpenRouter (OpenAI compatible) API adapter - supports streaming analysis"""
    
    TEMPLATE_MAP = {
        'github': 'github_expert',
        'hf': 'hf_explorer',
        'ph': 'ph_hunter',
    }
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.api_key = Config.OPENROUTER_API_KEY
        self.model = Config.OPENROUTER_MODEL
        self.base_url = Config.OPENROUTER_BASE_URL
        self.max_content_length = Config.MAX_CONTENT_LENGTH
        
        if cache_dir is None:
            cache_dir = Config.CACHE_DIR
        
        os.makedirs(cache_dir, exist_ok=True)
        self.cache = Cache(cache_dir)
        self.prompt_loader = PromptLoader()

        # Initialize persistent client (connection pool)
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        timeout = httpx.Timeout(Config.REQUEST_TIMEOUT, connect=10.0)
        self.client = httpx.AsyncClient(limits=limits, timeout=timeout, http2=False)
        
        # Rate limiting protection state
        self.rate_limiter = get_openrouter_rate_limiter()
    
    def _prepare_content(self, content: str) -> str:
        if len(content) > self.max_content_length:
            return content[:self.max_content_length] + "...[content truncated]"
        return content

    async def _wait_for_rate_limit(self):
        """Hard rate limiting logic: ensure at least Config.MIN_REQUEST_INTERVAL between two requests"""
        await self.rate_limiter.acquire()

    async def analyze_async(self, source: str, name: str, content: str, chunk_callback: Optional[Callable[[str], None]] = None) -> str:
        """
        Asynchronously analyze content with streaming, with automatic retry mechanism.
        """
        if not self.api_key:
            return "⚠️ OPENROUTER_API_KEY not configured"
        
        processed_content = self._prepare_content(content)
        cache_key = generate_cache_key(source, name, processed_content, self.model)
        
        if cache_key in self.cache:
            result = str(self.cache[cache_key])
            if chunk_callback:
                chunk_callback(result)
            return result
        
        # 1. Before making the formal request, perform hard rate limit check (5 second interval)
        template_name = self.TEMPLATE_MAP.get(source, 'github_expert')
        system_prompt = self.prompt_loader.load(template_name)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please analyze the following item:\n\n**Item Name**: {name}\n\n**Content**:\n{processed_content}"}
        ]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max(256, min(4096, Config.AI_COMMENT_MAX_TOKENS)),
            "temperature": 0.7,
            "stream": True,
        }
        if Config.OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON:
            try:
                extra = json.loads(Config.OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON)
                if isinstance(extra, dict):
                    payload.update(extra)
            except json.JSONDecodeError:
                logger.warning("OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON is invalid JSON, ignoring.")
        
        max_retries = Config.MAX_RETRIES
        for attempt in range(max_retries):
            full_response = ""
            reasoning_buffer = ""
            try:
                # 2. Reuse persistent self.client to improve handshake efficiency
                await self._wait_for_rate_limit()
                async with self.client.stream("POST", self.base_url + "/chat/completions", headers=headers, json=payload) as response:
                    if response.status_code == 429:
                        # Encountered 429 rate limit, execute heavy penalty wait
                        wait_time = Config.OPENROUTER_429_COOLDOWN_SECONDS
                        logger.warning("[RATE LIMIT] %s triggered rate limit, waiting %ss for penalty...", name, wait_time)
                        self.rate_limiter.enter_cooldown(wait_time)
                        continue

                    if response.status_code != 200:
                        return f"❌ AI API error ({response.status_code})"

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                            
                        try:
                            data = json.loads(data_str)
                            if data.get('choices') and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta') or {}
                                chunk = _extract_stream_text_from_delta(delta, include_reasoning=False)
                                if Config.OPENROUTER_STREAM_FALLBACK_TO_REASONING:
                                    reasoning_buffer += _extract_delta_reasoning_only(delta)
                                if chunk:
                                    full_response += chunk
                                    if chunk_callback:
                                        chunk_callback(chunk)
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue

                text_out = full_response.strip()
                if not text_out and Config.OPENROUTER_STREAM_FALLBACK_TO_REASONING and reasoning_buffer.strip():
                    text_out = reasoning_buffer.strip()
                if text_out:
                    self.cache[cache_key] = text_out
                    return text_out
                
            except (httpx.TimeoutException, httpx.TransportError, httpx.LocalProtocolError, httpx.RemoteProtocolError) as e:
                # 3. Enhanced exception handling: include timeout and perform exponential backoff
                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        "[RETRY] %s request error (%s), will retry %s in %ss...",
                        name,
                        type(e).__name__,
                        attempt + 1,
                        wait_time,
                    )
                    if attempt > 0:
                        logger.warning("[RETRY] Recreating client connection to avoid stale connection")
                        await self.client.aclose()
                        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
                        timeout = httpx.Timeout(Config.REQUEST_TIMEOUT, connect=10.0)
                        self.client = httpx.AsyncClient(limits=limits, timeout=timeout, http2=False)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return f"❌ Network connection repeatedly interrupted: {str(e)}"
            except Exception as e:
                return f"❌ Unexpected error: {str(e)}"
        
        return "❌ Exceeded maximum retry attempts"

    def analyze(self, source: str, name: str, content: str, stream: bool = False) -> str:
        """Synchronous method (kept for compatibility)"""
        return "Please use the async method analyze_async"

    def clear_cache(self):
        self.cache.clear()
    
    def get_cache_size(self) -> int:
        return sum(1 for _ in self.cache.iterkeys())

    async def complete_async(
        self,
        system_prompt: str,
        user_content: str,
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.4,
    ) -> str:
        if not self.api_key:
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": max_tokens or 1024,
            "temperature": temperature,
            "stream": False,
        }
        if Config.OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON:
            try:
                extra = json.loads(Config.OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON)
                if isinstance(extra, dict):
                    payload.update(extra)
            except json.JSONDecodeError:
                logger.warning("OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON is not valid JSON, ignoring.")

        for attempt in range(Config.MAX_RETRIES):
            try:
                await self._wait_for_rate_limit()
                response = await self.client.post(
                    self.base_url + "/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if response.status_code == 429:
                    wait_time = Config.OPENROUTER_429_COOLDOWN_SECONDS
                    self.rate_limiter.enter_cooldown(wait_time)
                    logger.warning("[RATE LIMIT] Overview request triggered rate limit, entering %.1f second cooldown.", wait_time)
                    continue

                response.raise_for_status()
                payload_json = response.json()
                choices = payload_json.get("choices") or []
                if not choices:
                    return ""

                message = choices[0].get("message") or {}
                return str(message.get("content") or "").strip()
            except (httpx.TimeoutException, httpx.TransportError, httpx.LocalProtocolError, httpx.RemoteProtocolError) as e:
                if attempt < Config.MAX_RETRIES - 1:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        "[RETRY] Overview request error (%s), will retry in %.1f seconds.",
                        type(e).__name__,
                        wait_time,
                    )
                    if attempt > 0:
                        await self.client.aclose()
                        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
                        timeout = httpx.Timeout(Config.REQUEST_TIMEOUT, connect=10.0)
                        self.client = httpx.AsyncClient(limits=limits, timeout=timeout, http2=False)
                    await asyncio.sleep(wait_time)
                    continue
                return ""
            except Exception as e:
                logger.warning("Overview generation failed: %s", e)
                return ""

        return ""

def get_adapter() -> OpenRouterAdapter:
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = OpenRouterAdapter()
    return _adapter_instance
