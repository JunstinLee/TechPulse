import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.config import Config
from utils.openrouter_rate_limiter import get_openrouter_rate_limiter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe OpenRouter with the current project concurrency pattern."
    )
    parser.add_argument("--requests", type=int, default=6, help="Total requests to send.")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Concurrent workers. Match pipeline semaphore with 3 by default.",
    )
    parser.add_argument(
        "--use-limiter",
        action="store_true",
        default=True,
        help="Use the shared OpenRouterRateLimiter before each request.",
    )
    parser.add_argument("--no-limiter", action="store_false", dest="use_limiter")
    parser.add_argument(
        "--stream",
        action="store_true",
        default=True,
        help="Use stream=True to match analyze_async.",
    )
    parser.add_argument("--no-stream", action="store_false", dest="stream")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=64,
        help="Keep outputs small so raw responses stay readable.",
    )
    parser.add_argument(
        "--prompt",
        default="Reply with exactly one short sentence that says hello.",
        help="User message sent to OpenRouter.",
    )
    parser.add_argument(
        "--system-prompt",
        default="You are a concise assistant.",
        help="System prompt sent to OpenRouter.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join("data", "openrouter_probe"),
        help="Directory for JSONL probe logs.",
    )
    parser.add_argument(
        "--body-char-limit",
        type=int,
        default=4000,
        help="Max characters of raw response body saved per request.",
    )
    return parser


def sanitize_headers(headers: httpx.Headers) -> dict[str, str]:
    return {k: v for k, v in headers.items()}


async def capture_stream_response(
    response: httpx.Response,
    body_char_limit: int,
) -> dict[str, Any]:
    lines: list[str] = []
    body_parts: list[str] = []
    done_seen = False

    async for line in response.aiter_lines():
        if line is None:
            continue
        lines.append(line)
        body_parts.append(line + "\n")
        if line.strip() == "data: [DONE]":
            done_seen = True
            break
        if sum(len(part) for part in body_parts) >= body_char_limit:
            break

    raw_body = "".join(body_parts)[:body_char_limit]
    return {
        "raw_body": raw_body,
        "stream_done_seen": done_seen,
        "stream_line_count": len(lines),
    }


async def capture_non_stream_response(
    response: httpx.Response,
    body_char_limit: int,
) -> dict[str, Any]:
    text = await response.aread()
    raw_body = text.decode("utf-8", errors="replace")[:body_char_limit]
    return {
        "raw_body": raw_body,
        "stream_done_seen": False,
        "stream_line_count": 0,
    }


async def send_one_request(
    request_id: int,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    args: argparse.Namespace,
) -> dict[str, Any]:
    limiter = get_openrouter_rate_limiter()
    payload = {
        "model": Config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": args.system_prompt},
            {"role": "user", "content": args.prompt},
        ],
        "max_tokens": args.max_tokens,
        "temperature": 0.0,
        "stream": args.stream,
    }
    headers = {
        "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if args.stream else "application/json",
    }

    async with semaphore:
        queued_at = time.time()
        if args.use_limiter:
            await limiter.acquire()
        send_started_at = time.time()

        result: dict[str, Any] = {
            "request_id": request_id,
            "queued_at": queued_at,
            "send_started_at": send_started_at,
            "limiter_enabled": args.use_limiter,
            "stream": args.stream,
            "model": Config.OPENROUTER_MODEL,
        }

        try:
            if args.stream:
                async with client.stream(
                    "POST",
                    f"{Config.OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    result["status_code"] = response.status_code
                    result["headers"] = sanitize_headers(response.headers)
                    body_info = await capture_stream_response(response, args.body_char_limit)
                    result.update(body_info)
            else:
                response = await client.post(
                    f"{Config.OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                result["status_code"] = response.status_code
                result["headers"] = sanitize_headers(response.headers)
                body_info = await capture_non_stream_response(response, args.body_char_limit)
                result.update(body_info)
        except Exception as exc:
            result["exception_type"] = type(exc).__name__
            result["exception_message"] = str(exc)

        result["finished_at"] = time.time()
        result["elapsed_seconds"] = round(result["finished_at"] - send_started_at, 3)
        return result


async def main() -> None:
    args = build_parser().parse_args()

    if not Config.OPENROUTER_API_KEY:
        raise SystemExit("OPENROUTER_API_KEY is missing.")

    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(args.output_dir, f"openrouter_probe_{timestamp}.jsonl")

    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    timeout = httpx.Timeout(Config.REQUEST_TIMEOUT, connect=10.0)
    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        tasks = [
            send_one_request(request_id=i + 1, client=client, semaphore=semaphore, args=args)
            for i in range(args.requests)
        ]
        results = await asyncio.gather(*tasks)

    with open(output_path, "w", encoding="utf-8") as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Saved raw probe results to: {output_path}")
    for item in results:
        status = item.get("status_code", "EXC")
        elapsed = item.get("elapsed_seconds", "n/a")
        exc = item.get("exception_type")
        suffix = f" | exception={exc}" if exc else ""
        print(
            f"request={item['request_id']} status={status} elapsed={elapsed}s"
            f" limiter={item['limiter_enabled']} stream={item['stream']}{suffix}"
        )


if __name__ == "__main__":
    asyncio.run(main())
