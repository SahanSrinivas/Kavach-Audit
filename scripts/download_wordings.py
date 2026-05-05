"""Bulk-download official insurer wording PDFs.

For each (insurer, plan, source_url), fetches the PDF, validates it
(magic bytes + size band 100KB-25MB), and saves to:

    wordings/{insurer_slug}/{plan_slug}.pdf

Source URLs are hardcoded below — discovered via Google site: searches
against each insurer's official domain (`{insurer} {plan} policy wording
PDF site:{insurer_domain}`) and recorded once so the script is fully
reproducible from a fresh checkout.

The wordings/ tree is gitignored (.gitignore has a global *.pdf rule
from the PII work in the dashboard sequence). The download log goes
to wordings/_download_log.txt as plain text — that file IS gitignored
since it lives under wordings/, but it's a runtime artifact anyway.

Usage:
    python scripts/download_wordings.py
"""
from __future__ import annotations

import base64
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. pip install requests", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
WORDINGS_DIR = REPO_ROOT / "wordings"
LOG_PATH = WORDINGS_DIR / "_download_log.txt"
ENV_PATH = REPO_ROOT / "backend" / ".env"

# Validation bands. PDF magic bytes are checked first — anything that
# isn't a real PDF (HTML error page, redirect to login, etc.) gets
# rejected with a clear reason.
PDF_MAGIC = b"%PDF-"
MIN_BYTES = 100 * 1024              # 100 KB
MAX_BYTES = 25 * 1024 * 1024        # 25 MB

# Some insurer CDNs reject default Python User-Agent with 403/406. A
# realistic UA gets us past the basic guards. Timeout is generous
# because government insurer sites (newindia, uiic, oriental, national)
# are notoriously slow.
HTTP_TIMEOUT = 60.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class WordingTarget:
    insurer: str            # canonical name (matches CANONICAL_INSURER_NAMES)
    plan: str               # plan name as marketed
    url: str                # source URL (validated by hand from web search)
    domain: str             # insurer domain (used for fallback search hint)
    # Optional explicit Referer override. When omitted, defaults to
    # https://www.{domain}/ — most CDNs accept either the bare domain
    # or the product page. The override is for cases like Star Health's
    # CDN (web.starhealth.in) which rejects requests without a referer
    # from the main marketing site.
    referer: Optional[str] = None


# Found via WebSearch against `{insurer} {plan} policy wording PDF
# site:{domain}`. First .pdf-bearing result chosen for each. URLs were
# verified at script-write time; insurers occasionally rotate paths so
# rebuild this list when a 404 appears in the log.
TARGETS: list[WordingTarget] = [
    WordingTarget(
        "HDFC ERGO General", "Optima Secure",
        "https://www.hdfcergo.com/docs/default-source/downloads/policy-wordings/health/optima-secure-revision-pw.pdf",
        "hdfcergo.com",
    ),
    WordingTarget(
        "Star Health", "Comprehensive",
        # web.starhealth.in returns 403 with or without referer — Akamai
        # bot-detection. The IRDAI-filed copy of the same wording (V.13,
        # UIN SHAHLIP22028V072122) is the regulator-authoritative source.
        "https://irdai.gov.in/documents/37343/931203/SHAHLIP22028V072122_HEALTH2050.pdf/70aade12-d528-1155-a8b7-c03d2cfecd15?version=1.1&t=1668769970678&download=true",
        "starhealth.in",
    ),
    WordingTarget(
        "Care Health", "Supreme",
        "https://cms.careinsurance.com/cms/public/uploads/download_center/care-supreme---policy-terms-and-conditions.pdf",
        "careinsurance.com",
    ),
    WordingTarget(
        "Niva Bupa", "ReAssure 2.0 Platinum+",
        "https://transactions.nivabupa.com/pages/doc/policy_wording/ReAssure-2.0-Policy-Wording.pdf",
        "nivabupa.com",
    ),
    WordingTarget(
        "Aditya Birla Health", "Activ One MAX",
        "https://www.adityabirlacapital.com/healthinsurance/assets/pdf/active-one/NXT/product-information/policy-document.pdf",
        "adityabirlacapital.com",
    ),
    WordingTarget(
        "ICICI Lombard", "Elevate",
        # Elevate is a 2024 product (UIN ICIHLIP25048V042425) — too new
        # for IRDAI's mirror, only available on icicilombard.com which
        # has Akamai bot-detection. The full Sec-Fetch-* + sec-ch-ua-*
        # fingerprint added in fetch() should clear the basic check.
        "https://www.icicilombard.com/docs/default-source/apps/elevateapp/assets/pdf/elevate-policy-wordings.pdf",
        "icicilombard.com",
        referer="https://www.icicilombard.com/health-insurance/elevate-health-policy",
    ),
    WordingTarget(
        "Tata AIG General", "MediCare Premier",
        "https://www.tataaig.com/s3/Tata_AIG_Medi_Care_Premier_2f02f3813c.pdf",
        "tataaig.com",
    ),
    WordingTarget(
        "Bajaj Allianz General", "Health Guard",
        "https://www.bajajallianz.com/download-documents/health-insurance/health-guard/Health-Guard-Policy-Wordings-print.pdf",
        "bajajallianz.com",
    ),
    WordingTarget(
        "ManipalCigna", "ProHealth Prime",
        # The manipalcigna.com Liferay URL we tried first 404'd. This
        # is the IRDAI-filed copy of the same wording (UIN
        # MCIHLIP22224V012122) — IRDAI is the regulator and IS the
        # authoritative source, so this is a legitimate substitute.
        "https://irdai.gov.in/documents/37343/931203/MCIHLIP22224V012122.pdf/6cf0a1af-1bc8-0c09-531a-671e15963135?version=1.1&t=1668851840343&download=true",
        "manipalcigna.com",
    ),
    WordingTarget(
        "New India Assurance", "Floater Mediclaim",
        # URL contains spaces — encoded by quote() at fetch time.
        "https://www.newindia.co.in/assets/docs/know-more/health/floater-mediclaim-policy/Policy Clause New India Floater Mediclaim Policy wef 01 10 2024.pdf",
        "newindia.co.in",
    ),
    WordingTarget(
        "Star Health", "Senior Citizens Red Carpet",
        # IRDAI-filed copy (UIN SHAHLIP22199V062122) — same Akamai 403
        # workaround as Star Comprehensive above.
        "https://irdai.gov.in/documents/37343/931203/SHAHLIP22199V062122.pdf/e5830765-7541-0484-9119-330738250254?version=1.1&t=1668853579702&download=true",
        "starhealth.in",
    ),
    WordingTarget(
        "United India Insurance", "Family Medicare",
        # uiic.co.in is unreachable from most networks (genuinely flaky
        # PSU site). IRDAI-filed copy (UIN UIIHLIP22070V042122) is the
        # regulator-authoritative source.
        "https://irdai.gov.in/documents/37343/931203/UIIHLIP22070V042122_HEALTH2068.pdf/ade80179-0e46-3c62-a889-652663255c71?version=1.1&t=1668769400360&download=true",
        "uiic.co.in",
    ),
    WordingTarget(
        "Oriental Insurance", "Happy Family Floater",
        # IRDAI-filed copy of HFF-2021 (UIN OICHLIP22010V042223). The
        # orientalinsurance.org.in domain times out from most networks.
        "https://irdai.gov.in/documents/37343/931203/OICHLIP22010V042223.pdf/b8f4f473-3670-8936-c219-d87881338353?version=1.0&t=1669353756992&download=true",
        "orientalinsurance.org.in",
    ),
    WordingTarget(
        "National Insurance", "Mediclaim",
        # IRDAI-filed copy of NMP (UIN NICHLIP21166V042021). The
        # nationalinsurance.nic.co.in domain times out from most networks.
        "https://irdai.gov.in/documents/37343/931203/NICHLIP21166V042021_2020-2021.pdf/11efffcc-a037-8819-2d2a-dc210ddac550?version=1.1&t=1668663754897&download=true",
        "nationalinsurance.nic.co.in",
    ),
]


# --------------------------------------------------------------------------
# Slug helpers
# --------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    """Lowercase, replace non-alphanumerics with underscores, strip
    leading/trailing underscores. Stable across runs so re-running the
    script overwrites rather than duplicates."""
    return _SLUG_RE.sub("_", s.lower()).strip("_")


def encode_url(url: str) -> str:
    """Percent-encode any unsafe characters (e.g. spaces in the New
    India Assurance URL) while leaving already-encoded chars alone."""
    return quote(url, safe=":/?&=#%+")


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_pdf(data: bytes) -> Optional[str]:
    """Return None if valid, else a short error string."""
    if not data.startswith(PDF_MAGIC):
        head = data[:80].decode("ascii", errors="replace")
        return f"not_a_pdf (got bytes: {head!r})"
    if len(data) < MIN_BYTES:
        return f"too_small ({len(data)} bytes < {MIN_BYTES})"
    if len(data) > MAX_BYTES:
        return f"too_large ({len(data)} bytes > {MAX_BYTES})"
    return None


# --------------------------------------------------------------------------
# Logger
# --------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_log(lines: list[str]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------

def fetch(url: str, referer: Optional[str] = None) -> tuple[Optional[bytes], Optional[str]]:
    """Direct HTTP fetch. Returns (bytes, None) on success or
    (None, error_string) on failure. Some insurer CDNs need a referer
    header — caller can pass one explicitly.

    Sec-Fetch-* and sec-ch-ua-* headers added so Cloudflare/Akamai bot
    fingerprinting sees a complete Chrome request rather than the bare
    requests/python signature that triggers 403 on icicilombard.com."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # Brotli (br) requires the optional `brotli` package; without
        # it, requests returns undecoded br bytes that prefix the PDF
        # with garbage and validation thinks it's not a PDF. Stick to
        # gzip+deflate which requests handles natively.
        "Accept-Encoding": "gzip, deflate",
        "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    try:
        resp = requests.get(
            encode_url(url),
            headers=headers,
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
        )
    except requests.exceptions.SSLError as e:
        return None, f"ssl_error: {e!s}"
    except requests.exceptions.ConnectionError as e:
        return None, f"connection_error: {type(e).__name__}"
    except requests.exceptions.Timeout:
        return None, f"timeout (>{HTTP_TIMEOUT}s)"
    except requests.exceptions.RequestException as e:
        return None, f"request_error: {type(e).__name__}"

    if resp.status_code != 200:
        return None, f"http_{resp.status_code}"
    return resp.content, None


# --------------------------------------------------------------------------
# Firecrawl fallback
# --------------------------------------------------------------------------
# Used when the direct HTTP fetch fails (403 from a hotlink-protected
# CDN, connection timeout from a slow government insurer site, etc.).
# Firecrawl runs from datacenters with better routing and bypasses the
# basic guards that block our direct request.
#
# API: POST https://api.firecrawl.dev/v1/scrape with parsers:[] returns
# the raw file as base64. The exact field name in the response is
# poorly documented (firecrawl/firecrawl#1669) so we sniff for it
# rather than hardcode.

FIRECRAWL_URL = "https://api.firecrawl.dev/v2/scrape"
FIRECRAWL_TIMEOUT = 120.0


def load_firecrawl_key() -> Optional[str]:
    """Read FIRE_CRAWL from backend/.env. Returns None if env file or
    key is missing — caller treats absence as 'firecrawl unavailable'
    rather than crashing."""
    if not ENV_PATH.exists():
        return None
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == "FIRE_CRAWL":
            v = v.strip().strip('"').strip("'")
            return v or None
    # Also accept the more standard env var name as a fallback so future
    # rotations to FIRECRAWL_API_KEY don't break the script.
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("FIRECRAWL_API_KEY="):
            return line.partition("=")[2].strip().strip('"').strip("'") or None
    return None


def _walk_for_pdf(obj: Any) -> Optional[bytes]:
    """Recursively walk a JSON object looking for a string that
    base64-decodes to PDF bytes. Robust to firecrawl's response field
    drift (the docs don't pin down where the base64 lives — could be
    data.rawHtml, data.content, data.binary, etc.)."""
    if isinstance(obj, str):
        # Quick sniff before attempting decode — base64-encoded PDFs
        # always start with "JVBERi0" (which is "%PDF-" in base64).
        if obj.startswith("JVBERi0"):
            try:
                decoded = base64.b64decode(obj, validate=False)
                if decoded.startswith(PDF_MAGIC):
                    return decoded
            except Exception:                       # noqa: BLE001
                pass
        return None
    if isinstance(obj, dict):
        for v in obj.values():
            found = _walk_for_pdf(v)
            if found is not None:
                return found
        return None
    if isinstance(obj, list):
        for v in obj:
            found = _walk_for_pdf(v)
            if found is not None:
                return found
    return None


def firecrawl_fetch(url: str, api_key: str) -> tuple[Optional[bytes], Optional[str]]:
    """Try firecrawl v2 as a proxy. Returns (bytes, None) or (None, err).

    v2 reshaped the request — `parsers: []` from v1 became a config
    object `parsers: [{"type": "pdf", ...}]`. There's no documented
    "give me the raw bytes" knob in v2; we ask for `rawHtml` (the
    closest format that returns the unparsed response body) and let
    _walk_for_pdf hunt for any base64-PDF string in the JSON. If
    firecrawl hands back markdown instead, the sniffer returns None
    and the operator gets a "no PDF in response" hint."""
    try:
        resp = requests.post(
            FIRECRAWL_URL,
            json={"url": url, "formats": ["rawHtml"]},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=FIRECRAWL_TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        return None, f"firecrawl_request_error: {type(e).__name__}"

    if resp.status_code != 200:
        # Surface response body snippet for diagnosis (firecrawl
        # typically explains 4xx in the body).
        body = resp.text[:200].replace("\n", " ")
        return None, f"firecrawl_http_{resp.status_code}: {body}"

    try:
        payload = resp.json()
    except Exception:                               # noqa: BLE001
        return None, "firecrawl_non_json_response"

    pdf = _walk_for_pdf(payload)
    if pdf is None:
        # Sniffer found no base64 PDF anywhere in the response. Most
        # likely firecrawl returned the parsed markdown instead — log
        # a hint about the response keys so we can adjust.
        keys = list(payload.get("data", {}).keys()) if isinstance(payload, dict) else []
        return None, f"firecrawl_no_pdf_in_response (keys: {keys})"

    return pdf, None


def search_url_for(target: WordingTarget) -> str:
    """Google search URL the user can open if our hardcoded URL 404s
    or fails validation. The script can't re-search itself; this just
    points the operator at the right query."""
    q = f"{target.insurer} {target.plan} policy wording PDF site:{target.domain}"
    return f"https://www.google.com/search?q={quote(q)}"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def _try_fetch(t: WordingTarget, fc_key: Optional[str]) -> tuple[Optional[bytes], str, str]:
    """Try direct fetch; on any failure (network, HTTP error, validation),
    try firecrawl if available. Returns (bytes_or_none, source_label,
    error_string). source_label is 'direct', 'firecrawl', or '-'."""
    direct_referer = t.referer or f"https://www.{t.domain}/"
    body, err = fetch(t.url, referer=direct_referer)
    if body is not None and validate_pdf(body) is None:
        return body, "direct", ""
    direct_err = err or f"validation: {validate_pdf(body) if body else 'no_body'}"

    if fc_key is None:
        return None, "-", f"{direct_err} (firecrawl unavailable: no FIRE_CRAWL key)"

    fc_body, fc_err = firecrawl_fetch(t.url, fc_key)
    if fc_body is not None and validate_pdf(fc_body) is None:
        return fc_body, "firecrawl", ""
    fc_detail = fc_err or f"validation: {validate_pdf(fc_body) if fc_body else 'no_body'}"
    return None, "-", f"direct: {direct_err}; firecrawl: {fc_detail}"


def main() -> int:
    WORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    fc_key = load_firecrawl_key()
    log: list[str] = []
    log.append(f"# Wordings download log — {_now_iso()}")
    log.append(
        f"# {len(TARGETS)} targets, validation band {MIN_BYTES}-{MAX_BYTES} bytes, "
        f"firecrawl fallback: {'enabled' if fc_key else 'DISABLED (no key)'}"
    )
    log.append("")

    ok_direct = 0
    ok_firecrawl = 0
    failed = 0
    for t in TARGETS:
        insurer_slug = slugify(t.insurer)
        plan_slug = slugify(t.plan)
        out_dir = WORDINGS_DIR / insurer_slug
        out_path = out_dir / f"{plan_slug}.pdf"

        ts = _now_iso()
        started = time.perf_counter()
        body, source, err = _try_fetch(t, fc_key)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if body is None:
            failed += 1
            log.append(
                f"[{ts}] FAIL  {t.insurer} | {t.plan}\n"
                f"  url:    {t.url}\n"
                f"  error:  {err}  ({elapsed_ms}ms)\n"
                f"  next:   manually download from {search_url_for(t)}\n"
                f"          and save to {out_path.relative_to(REPO_ROOT)}"
            )
            print(f"FAIL  {t.insurer} / {t.plan}: {err}")
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(body)
        size = len(body)
        if source == "direct":
            ok_direct += 1
        else:
            ok_firecrawl += 1
        log.append(
            f"[{ts}] OK    {t.insurer} | {t.plan}  (via {source})\n"
            f"  url:    {t.url}\n"
            f"  size:   {size:,} bytes  ({elapsed_ms}ms)\n"
            f"  saved:  {out_path.relative_to(REPO_ROOT)}"
        )
        print(f"OK    {t.insurer} / {t.plan}: {size:,} bytes  (via {source})")

    log.append("")
    log.append(
        f"# Summary: {ok_direct + ok_firecrawl} ok "
        f"({ok_direct} direct, {ok_firecrawl} firecrawl), "
        f"{failed} failed (of {len(TARGETS)} targets)"
    )
    write_log(log)
    print(
        f"\n{ok_direct + ok_firecrawl} ok ({ok_direct} direct, {ok_firecrawl} firecrawl), "
        f"{failed} failed. Log → {LOG_PATH.relative_to(REPO_ROOT)}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
