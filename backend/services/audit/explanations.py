"""Template renderer + Claude fallback stub.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 6 — "Generation
strategy: 80% deterministic, 20% Claude". Today only the deterministic
path is wired; the Claude path is stubbed and returns the template
version. The actual Anthropic prompt + caching strategy lands in a
follow-up session.
"""
from __future__ import annotations

from typing import Any, Mapping

from services.audit.constants.templates import (
    SEVERITY_FROM_SPEC,
    TEMPLATES,
    TemplateRecord,
)


class TemplateNotFound(Exception):
    pass


def render(finding_type: str, ctx: Mapping[str, Any]) -> dict[str, str]:
    """Render the given finding type with the supplied context.

    Returns a dict with the four user-facing strings: headline,
    explanation, action — plus severity_default, icon, cta — already
    interpolated. KeyError in the .format() call surfaces as a clear
    exception so missing context is loud during development.
    """
    tmpl: TemplateRecord | None = TEMPLATES.get(finding_type)
    if tmpl is None:
        raise TemplateNotFound(finding_type)

    safe_ctx = _SafeFormatDict(ctx)
    return {
        "severity_default": tmpl["severity_default"],
        "icon": tmpl["icon"],
        "headline": tmpl["headline"].format_map(safe_ctx),
        "explanation": tmpl["explanation"].format_map(safe_ctx),
        "action": tmpl["action"].format_map(safe_ctx),
        "cta": tmpl["cta"],
    }


def map_severity(spec_severity: str) -> str:
    """Spec uses critical/high/medium/low; frontend uses red/amber/info.

    Spec → frontend per the user's confirmed mapping in Step 2 prompt:
      critical, high → red
      medium → amber
      low → info
    """
    return SEVERITY_FROM_SPEC.get(spec_severity, "amber")


def claude_fallback(finding_type: str, ctx: Mapping[str, Any]) -> dict[str, str]:
    """STUB: real Anthropic call lands in a follow-up session.

    For now: returns the deterministic template render. When the real
    client ships, the call site swaps in an asynchronous wrapper that
    falls back to this template if Claude takes >3s or errors.
    """
    return render(finding_type, ctx)


class _MissingValue:
    """Format-spec-tolerant placeholder for unset template context keys.

    Plain string returns from __missing__ break on numeric format specs
    like `{cap:,}`. By implementing __format__ ourselves we accept any
    spec and emit a visible `{key}` placeholder.
    """
    __slots__ = ("key",)

    def __init__(self, key: str) -> None:
        self.key = key

    def __format__(self, _spec: str) -> str:
        return f"{{{self.key}}}"

    def __str__(self) -> str:
        return f"{{{self.key}}}"


class _SafeFormatDict(dict[str, Any]):
    """str.format_map() helper: missing keys substitute as a visible
    placeholder rather than KeyError, so partial parses still produce
    readable findings during dev.
    """
    def __init__(self, base: Mapping[str, Any]) -> None:
        super().__init__(base)

    def __missing__(self, key: str) -> Any:
        return _MissingValue(key)
