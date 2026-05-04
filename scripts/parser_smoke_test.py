#!/usr/bin/env python3
"""End-to-end smoke test for the PDF parser.

Single real Claude API call against a sample policy PDF. Prints:
  1. The rich parser_output JSON (Claude's response, validated + normalized)
  2. The flat parsed_fields after to_engine_shape() adapter
  3. The confidence block (overall + fields_with_low_confidence + warnings)
  4. Total API call duration + token usage (input / output / total)

Usage:
  ANTHROPIC_API_KEY=sk-ant-... python3 scripts/parser_smoke_test.py <path/to/policy.pdf>

Or with the .env loaded:
  set -a && source backend/.env && set +a && python3 scripts/parser_smoke_test.py <pdf>

Cost: ~₹15-30 per call. Budget accordingly.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from services.parser.prompt_builder import build_parsing_prompt        # noqa: E402
from services.parser.response_validator import (                       # noqa: E402
    InvalidParseResponseError,
    to_engine_shape,
    validate_and_normalize,
)


CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
TEMPERATURE = 0.0
TIMEOUT_SECONDS = 60.0


async def main(pdf_path: Path) -> int:
    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} not found", file=sys.stderr)
        return 2
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    pdf_bytes = pdf_path.read_bytes()
    print(f"== INPUT ==")
    print(f"  file:      {pdf_path}")
    print(f"  size:      {len(pdf_bytes):,} bytes ({len(pdf_bytes)//1024} KB)")
    print(f"  model:     {CLAUDE_MODEL}")
    print(f"  prompt:    {len(build_parsing_prompt()):,} chars")

    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=api_key, timeout=TIMEOUT_SECONDS)

    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    prompt = build_parsing_prompt()

    started = time.perf_counter()
    message = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    elapsed_s = time.perf_counter() - started

    print()
    print(f"== TIMING & TOKEN USAGE ==")
    print(f"  duration:        {elapsed_s:.2f}s")
    if hasattr(message, "usage"):
        u = message.usage
        in_tok = getattr(u, "input_tokens", "?")
        out_tok = getattr(u, "output_tokens", "?")
        total = (in_tok if isinstance(in_tok, int) else 0) + (out_tok if isinstance(out_tok, int) else 0)
        print(f"  input_tokens:    {in_tok}")
        print(f"  output_tokens:   {out_tok}")
        print(f"  total_tokens:    {total}")
        # Sonnet 4 pricing (Mar 2026): $3 / 1M input, $15 / 1M output
        # ₹86 / USD assumed.
        if isinstance(in_tok, int) and isinstance(out_tok, int):
            usd = (in_tok * 3 + out_tok * 15) / 1_000_000
            print(f"  est_cost:        ${usd:.4f} USD  (~₹{usd*86:.2f})")

    # Extract text block (defensive against new content-block types)
    text = ""
    for b in message.content:
        if getattr(b, "type", None) == "text":
            text = getattr(b, "text", "")
            break
    if not text:
        print("\nERROR: Claude returned no text block", file=sys.stderr)
        return 1

    # Strip optional fences (prompt forbids them, but be defensive)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"\nERROR: Claude returned malformed JSON: {e}", file=sys.stderr)
        print("--- raw response ---", file=sys.stderr)
        print(text[:2000], file=sys.stderr)
        return 1

    print()
    print(f"== 1. RICH parser_output (Claude raw, after validate_and_normalize) ==")
    try:
        parsed = validate_and_normalize(raw)
    except InvalidParseResponseError as e:
        print(f"ERROR: validation failed: {e}", file=sys.stderr)
        print("--- raw JSON ---", file=sys.stderr)
        print(json.dumps(raw, indent=2, ensure_ascii=False)[:3000], file=sys.stderr)
        return 1
    print(json.dumps(parsed.model_dump(), indent=2, default=str, ensure_ascii=False))

    print()
    print(f"== 2. FLAT parsed_fields (after to_engine_shape adapter) ==")
    flat = to_engine_shape(parsed)
    print(json.dumps(flat, indent=2, default=str, ensure_ascii=False))

    print()
    print(f"== 3. CONFIDENCE BLOCK ==")
    conf = parsed.confidence
    print(f"  overall:                       {conf.overall}")
    print(f"  fields_with_low_confidence:    {conf.fields_with_low_confidence}")
    print(f"  warnings ({len(conf.warnings)}):")
    for w in conf.warnings:
        print(f"    - {w}")

    print()
    print(f"== 4. CANONICAL INSURER MATCH ==")
    print(f"  insurer_name (canonical): {parsed.insurer_name}")
    print(f"  insurer_name_raw:         {parsed.insurer_name_raw}")
    if parsed.insurer_name == "_UNKNOWN":
        print("  ⚠  Insurer not canonicalized — engine will use _DEFAULT CSR (-15 deduction)")

    print()
    print(f"== SMOKE TEST PASSED ==")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
