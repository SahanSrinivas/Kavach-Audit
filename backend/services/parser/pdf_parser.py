"""Async entrypoint for PDF policy parsing via Claude.

Cost note: each parse runs ~₹15-30 (~$0.20-0.40) on Sonnet 4 with native
PDF support. With the rate limit of 5 parses/hr/user enforced in the
router, daily budget at 100 users × 1 parse ≈ ₹2,000.

Performance: end-to-end < 15s on a typical 5-10 page policy schedule.
The bulk of the latency is Claude's PDF processing (~5-10s); local code
adds <100ms.

Privacy: PDF bytes are sent to Anthropic's API. We never log the content,
and Claude's prompt explicitly forbids returning personal data outside
the structured covered_members[] array. See critical_rules in
prompt_builder.py.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from typing import Any

from services.parser.prompt_builder import build_parsing_prompt
from services.parser.response_validator import (
    InvalidParseResponseError,
    validate_and_normalize,
)
from services.parser.types import ParsedPolicy

logger = logging.getLogger("kavach.parser")


CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 4096
CLAUDE_TEMPERATURE = 0.0
CLAUDE_TIMEOUT_SECONDS = 30.0
RETRY_ATTEMPTS = 2          # plus the initial attempt = 3 total tries
RETRY_INITIAL_BACKOFF = 1.0


class ParseFailureError(Exception):
    """Surface-level error type the router catches and records."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


async def parse_policy_pdf(pdf_bytes: bytes, filename: str) -> ParsedPolicy:
    """Parse an Indian health insurance policy PDF.

    Returns a ParsedPolicy on success. Raises ParseFailureError on
    any unrecoverable error (API failure, schema violation, Claude-
    flagged unreadable/non-policy document).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ParseFailureError("missing_api_key", "ANTHROPIC_API_KEY not set")

    # Lazy import keeps Anthropic out of the import path when USE_MOCKS=true.
    try:
        from anthropic import AsyncAnthropic
    except ImportError as e:
        raise ParseFailureError("missing_dependency", f"anthropic SDK not installed: {e}") from e

    client = AsyncAnthropic(api_key=api_key, timeout=CLAUDE_TIMEOUT_SECONDS)
    prompt = build_parsing_prompt()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    file_kb = len(pdf_bytes) // 1024

    started = time.perf_counter()
    raw_json = await _call_with_retries(client, prompt, pdf_b64, filename, file_kb)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    try:
        parsed = validate_and_normalize(raw_json)
    except InvalidParseResponseError as e:
        logger.warning(
            "parser.invalid_response filename=%s file_kb=%d elapsed_ms=%d error=%s",
            filename, file_kb, elapsed_ms, str(e),
        )
        raise ParseFailureError("invalid_response", str(e)) from e

    logger.info(
        "parser.success filename=%s file_kb=%d elapsed_ms=%d insurer=%s confidence=%s warnings=%d",
        filename, file_kb, elapsed_ms,
        parsed.insurer_name, parsed.confidence.overall, len(parsed.confidence.warnings),
    )
    return parsed


async def _call_with_retries(
    client: Any,
    prompt: str,
    pdf_b64: str,
    filename: str,
    file_kb: int,
) -> dict[str, Any]:
    """Call Claude with up to RETRY_ATTEMPTS retries on transient errors."""
    # Lazy import to keep optional dep out of the module-level path.
    try:
        from anthropic import APIError, APIStatusError, APITimeoutError
    except ImportError:
        # Fallback to bare Exception classes if the SDK isn't installed.
        # _call_with_retries shouldn't be reachable without the SDK, but
        # we want graceful degradation in test paths.
        APIError = APIStatusError = APITimeoutError = Exception  # type: ignore[assignment,misc]

    backoff = RETRY_INITIAL_BACKOFF
    last_exc: Exception | None = None

    for attempt in range(RETRY_ATTEMPTS + 1):
        try:
            logger.info(
                "parser.api_call attempt=%d filename=%s file_kb=%d",
                attempt + 1, filename, file_kb,
            )
            message = await client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                temperature=CLAUDE_TEMPERATURE,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            return _extract_json(message)
        except APITimeoutError as e:
            last_exc = e
            logger.warning("parser.timeout attempt=%d filename=%s", attempt + 1, filename)
        except APIStatusError as e:
            last_exc = e
            status = getattr(e, "status_code", 0)
            if status and 400 <= status < 500 and status not in (408, 429):
                # 4xx (excl. 408 timeout, 429 rate limit) is permanent — don't retry
                raise ParseFailureError(
                    "api_4xx",
                    f"Claude API returned {status}: {e}",
                ) from e
            logger.warning(
                "parser.api_status attempt=%d filename=%s status=%s",
                attempt + 1, filename, status,
            )
        except APIError as e:
            last_exc = e
            logger.warning("parser.api_error attempt=%d filename=%s error=%s",
                           attempt + 1, filename, type(e).__name__)

        if attempt < RETRY_ATTEMPTS:
            await asyncio.sleep(backoff)
            backoff *= 2

    raise ParseFailureError(
        "api_unavailable",
        f"Claude API failed after {RETRY_ATTEMPTS + 1} attempts: {last_exc}",
    )


def _extract_json(message: Any) -> dict[str, Any]:
    """Pull the first JSON object out of Claude's response."""
    if not message.content:
        raise ParseFailureError("empty_response", "Claude returned no content blocks")
    text = ""
    for block in message.content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text = getattr(block, "text", "")
            break
    if not text:
        raise ParseFailureError("empty_response", "Claude returned no text block")

    # Strip optional markdown fencing, just in case (the prompt forbids it
    # but we're defensive at the boundary).
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        parsed: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as e:
        raise ParseFailureError(
            "malformed_json",
            f"Claude response was not valid JSON: {e.msg} at pos {e.pos}",
        ) from e
    if not isinstance(parsed, dict):
        raise ParseFailureError(
            "malformed_json",
            f"Claude response is not a JSON object (got {type(parsed).__name__})",
        )
    return parsed
