from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure utils from the project root can be imported when running directly from the test/ subdirectory
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import httpx

from utils.ai_adapter import _extract_stream_text_from_delta
from utils.config import Config


def _build_payload(model: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Short messages to reduce queuing and prompt processing time, facilitating comparison of network and inference latency."""
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "Reply briefly."},
            {"role": "user", "content": "Count from 1 to 3 in one short line."},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }


async def _one_round(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
) -> Tuple[float, float, int]:
    """
    Single streaming request: returns (TTFT in seconds, total duration in seconds, total characters).

    TTFT: From initiating POST until receiving the first non-empty delta text fragment.
    """
    t_start = time.perf_counter()
    t_first: Optional[float] = None
    total_chars = 0

    async with client.stream("POST", url, headers=headers, json=payload) as response:
        if response.status_code != 200:
            body = await response.aread()
            raise RuntimeError(
                f"HTTP {response.status_code}: {body.decode(errors='replace')[:500]}"
            )

        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                # Benchmark "any streaming text" first packet: consistent with history, merge reasoning + content
                chunk = _extract_stream_text_from_delta(delta, include_reasoning=True)
                if chunk:
                    if t_first is None:
                        t_first = time.perf_counter()
                    total_chars += len(chunk)
            except (json.JSONDecodeError, IndexError, KeyError):
                continue

    t_end = time.perf_counter()
    if t_first is None:
        raise RuntimeError("Stream ended without receiving any text delta, unable to calculate TTFT")
    return (t_first - t_start, t_end - t_start, total_chars)


async def run_benchmark(
    rounds: int,
    warmup: int,
    max_tokens: int,
    temperature: float,
    *,
    concurrent: bool,
    concurrency: int,
    verbose: bool,
) -> None:
    api_key = Config.OPENROUTER_API_KEY
    if not api_key:
        print("OPENROUTER_API_KEY not configured. Please set it in .env and try again.")
        sys.exit(1)

    model = Config.OPENROUTER_MODEL
    base = Config.OPENROUTER_BASE_URL.rstrip("/")
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload = _build_payload(model, max_tokens=max_tokens, temperature=temperature)

    n_parallel = concurrency if concurrent else 1
    conn_limit = max(10, n_parallel + 4)
    limits = httpx.Limits(
        max_connections=conn_limit,
        max_keepalive_connections=max(5, n_parallel),
    )
    timeout = httpx.Timeout(Config.REQUEST_TIMEOUT, connect=10.0)

    ttft_list: List[float] = []
    total_list: List[float] = []
    chars_list: List[int] = []

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        for i in range(warmup):
            if verbose:
                print(f"[warmup {i + 1}/{warmup}] Warmup request...")
            await _one_round(client, url, headers, payload)

        if not concurrent:
            for i in range(rounds):
                if verbose:
                    print(f"[round {i + 1}/{rounds}] Single request...")
                ttft, total_s, nchars = await _one_round(client, url, headers, payload)
                ttft_list.append(ttft)
                total_list.append(total_s)
                chars_list.append(nchars)
                if verbose:
                    tps_after = (
                        (nchars / (total_s - ttft)) if (total_s - ttft) > 1e-6 else 0.0
                    )
                    print(
                        f"  TTFT={ttft * 1000:.1f} ms | Total Time={total_s * 1000:.1f} ms | "
                        f"Chars={nchars} | Approx. Throughput Post-TTFT≈{tps_after:.1f} chars/s"
                    )
        else:
            for i in range(rounds):
                if verbose:
                    print(f"[round {i + 1}/{rounds}] Concurrent {concurrency} ways...")
                results = await asyncio.gather(
                    *(
                        _one_round(client, url, headers, payload)
                        for _ in range(concurrency)
                    )
                )
                for j, (ttft, total_s, nchars) in enumerate(results, start=1):
                    ttft_list.append(ttft)
                    total_list.append(total_s)
                    chars_list.append(nchars)
                    if verbose:
                        tps_after = (
                            (nchars / (total_s - ttft)) if (total_s - ttft) > 1e-6 else 0.0
                        )
                        print(
                            f"  #{j} TTFT={ttft * 1000:.1f} ms | Total Time={total_s * 1000:.1f} ms | "
                            f"Chars={nchars} | Approx. Throughput Post-TTFT≈{tps_after:.1f} chars/s"
                        )
                batch_ttft_ms = [r[0] * 1000 for r in results]
                if verbose:
                    print(
                        f"  Batch TTFT (ms): min={min(batch_ttft_ms):.1f} | "
                        f"max={max(batch_ttft_ms):.1f} | mean={statistics.mean(batch_ttft_ms):.1f}"
                    )

    mode_label = "Concurrent" if concurrent else "Sequential"
    mode_line = mode_label + (f" ({concurrency} ways per round)" if concurrent else "")
    lines: List[str] = [
        "",
        f"Model: {model}",
        f"Endpoint: {url}",
        f"Mode: {mode_line}",
        f"Rounds: {rounds} (Warmup {warmup})",
    ]
    if ttft_list:
        ms = [x * 1000 for x in ttft_list]
        lines.append(
            "TTFT (ms): min={:.1f} | max={:.1f} | mean={:.1f} | stdev={:.1f}".format(
                min(ms),
                max(ms),
                statistics.mean(ms),
                statistics.stdev(ms) if len(ms) > 1 else 0.0,
            )
        )
    if total_list:
        tms = [x * 1000 for x in total_list]
        lines.append(
            "Total Time (ms): min={:.1f} | max={:.1f} | mean={:.1f}".format(
                min(tms), max(tms), statistics.mean(tms)
            )
        )
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenRouter Streaming TTFT and Throughput Benchmark")
    parser.add_argument(
        "--mode",
        choices=("sequential", "concurrent"),
        default="concurrent",
        help="sequential=Single sequential; concurrent=Multi-way concurrent per round (default: concurrent)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Number of parallel ways per round in concurrent mode (default: 3, only takes effect with --mode concurrent)",
    )
    parser.add_argument("--rounds", type=int, default=1, help="Number of measurement rounds (default: 1)")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print details for warmup, each round, and each way; default prints summary once at the end",
    )
    parser.add_argument("--warmup", type=int, default=0, help="Number of warmup requests, not counted in stats (default: 0)")
    parser.add_argument("--max-tokens", type=int, default=256, help="max_tokens (default: 256)")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="temperature (default: 0.3 for stability)",
    )
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")
    if args.warmup < 0:
        parser.error("--warmup cannot be negative")
    concurrent = args.mode == "concurrent"
    if concurrent and args.concurrency < 2:
        parser.error("In concurrent mode, --concurrency must be at least 2")

    asyncio.run(
        run_benchmark(
            rounds=args.rounds,
            warmup=args.warmup,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            concurrent=concurrent,
            concurrency=args.concurrency if concurrent else 1,
            verbose=args.verbose,
        )
    )


if __name__ == "__main__":
    main()