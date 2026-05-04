"""Regression tests for the prompt builder.

The smoke-test bug ("KeyError: '\"type\"'") was a Python str.format()
treating literal JSON braces in the template as substitution placeholders.
The fix switched to str.replace(); these tests enforce the contract so
the bug can't recur.
"""
from __future__ import annotations

from services.parser.prompt_builder import (
    _PROMPT_TEMPLATE,
    build_parsing_prompt,
)


# ---------- Build contract ----------

def test_build_parsing_prompt_returns_full_string() -> None:
    """Function returns a non-empty prompt string. The smoke-test bug
    raised before this line would have asserted len > 0."""
    prompt = build_parsing_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 5_000, f"prompt too short: {len(prompt)} chars"


def test_build_parsing_prompt_substitutes_canonical_insurers() -> None:
    """The single substitution token must be replaced — its absence in
    the output means .replace() ran."""
    prompt = build_parsing_prompt()
    assert "{canonical_insurers}" not in prompt, \
        "substitution placeholder was not replaced"


def test_build_parsing_prompt_preserves_json_examples() -> None:
    """Literal JSON in the template (single-brace) must reach Claude
    verbatim. If the prompt builder reverts to .format(), these would
    be misinterpreted as placeholders or escape-doubled."""
    prompt = build_parsing_prompt()
    # Schema-block literal JSON: opening braces of nested objects survive
    assert '"covered_members": [\n    {\n      "name"' in prompt
    assert '"parsed_fields": {' in prompt
    assert '"room_rent_cap": {' in prompt
    assert '"icu_cap": {' in prompt
    assert '"restoration_benefit": {' in prompt
    assert '"ncb_structure": {' in prompt
    assert '"confidence": {' in prompt
    # Schema enum descriptors (single-brace value-side strings)
    assert '"type": "enum — fixed_amount' in prompt
    assert '"available": "boolean"' in prompt
    # Rule #13 inline JSON examples (the closest analogue to the smoke-test trigger)
    assert '{"type": "fixed_amount", "value": 5000, "raw_text": null}' in prompt
    assert '{"type": null, "value": null, "raw_text": null}' in prompt
    # Critical-rules error envelopes must arrive as valid JSON examples
    assert '{"error": "not_an_indian_insurance_policy"' in prompt
    assert '{"error": "document_unreadable"' in prompt
    # The "first character must be '{'" rule must read as a single brace
    assert "first character of your response must be '{'" in prompt


def test_template_has_no_doubled_braces() -> None:
    """If anyone re-introduces .format()-style escapes, this test fails
    immediately. Caught at module load time too via the assertion in
    prompt_builder.py — this test makes the contract explicit in pytest.
    """
    assert "{{" not in _PROMPT_TEMPLATE, \
        "template contains '{{' — .replace() doesn't need brace escaping"
    assert "}}" not in _PROMPT_TEMPLATE, \
        "template contains '}}' — .replace() doesn't need brace escaping"


def test_template_has_exactly_one_substitution_token() -> None:
    """Only `{canonical_insurers}` is meant to be substituted. Any other
    `{name}`-shaped token would be either silently emitted to Claude
    (wrong) or unintentionally replaced (also wrong) if the substitution
    list grows. Today's contract: one and only one token."""
    import re
    # Match {bare_word} only — excludes JSON object braces because those
    # are followed immediately by a quote or newline, not a word char.
    tokens = re.findall(r"\{([a-z_][a-z_0-9]*)\}", _PROMPT_TEMPLATE)
    assert tokens == ["canonical_insurers"], \
        f"expected exactly ['canonical_insurers'] tokens, got {tokens}"


# ---------- Idempotency ----------

def test_build_parsing_prompt_includes_plan_name_extraction_rule() -> None:
    """The wordings DB joins on plan_name. If anyone removes the
    extraction rule, lookup hit-rate goes to ~0% silently."""
    prompt = build_parsing_prompt()
    assert '"plan_name"' in prompt
    assert '"plan_name_raw"' in prompt
    # Rule #17 — substring spot-check so a refactor that drops the rule
    # explanation (not just the schema entry) still fails this test
    assert "join key" in prompt or "wordings" in prompt
    # Worked examples must appear so Claude knows what cleaned vs verbatim look like
    assert "Optima Restore" in prompt


def test_build_parsing_prompt_is_deterministic() -> None:
    """Same template + same canonical list → identical output every call."""
    a = build_parsing_prompt()
    b = build_parsing_prompt()
    assert a == b


# ---------- Smoke-test-bug specific ----------

def test_build_parsing_prompt_does_not_raise_on_literal_json() -> None:
    """The exact crash mode the smoke test surfaced. If this raises
    KeyError, the prompt builder is broken in the same way as before."""
    try:
        build_parsing_prompt()
    except KeyError as e:
        raise AssertionError(
            f"prompt builder raised KeyError({e!r}) on literal JSON braces "
            f"— the .format()-style bug regressed."
        )
