"""Synthetic PDF generators for life preflight and `/life/extract` tests.

Keeps payloads >= ``MIN_FILE_BYTES`` (10 KiB) wherever structural checks apply.
Uses PyMuPDF (``fitz``) only — mirrors production ``pymupdf`` ingestion.
"""

from __future__ import annotations

import os
import tempfile

MIN_PAYLOAD_BYTES_DEFAULT = 10 * 1024


def sized_text_pdf(main_block: str, *, min_bytes: int = MIN_PAYLOAD_BYTES_DEFAULT) -> bytes:
    """First page carries ``main_block`` lines; filler pages inflate file size."""
    import fitz

    doc = fitz.open()
    try:
        page_idx = 0
        while True:
            page = doc.new_page()
            y = 72
            if page_idx == 0:
                for line in main_block.split("\n"):
                    page.insert_text((72, y), line)
                    y += 10
                    if y > 720:
                        break
            chunk = page_idx * 48
            for i in range(48):
                page.insert_text((72, y), f"filler paragraph {chunk + i:04d} row text")
                y += 10
                if y > 740:
                    break
            page_idx += 1
            raw = doc.tobytes()
            if len(raw) >= min_bytes:
                return raw
            if page_idx > 40:
                raise RuntimeError("sized_text_pdf: could not reach min_bytes")
    finally:
        doc.close()


def mini_borderline_life_pdf(min_bytes: int = MIN_PAYLOAD_BYTES_DEFAULT) -> bytes:
    """CIS-shaped text tuned to score in the humility band (~40) in preflight."""
    cis_header = (
        "Sum Assured Rs. 50,00,000\nPolicy Term 25 years\n"
        "Modal Premium Rs. 12,000 yearly\nNominee as per proposal"
    )
    import fitz

    doc = fitz.open()
    try:
        page_idx = 0
        while True:
            page = doc.new_page()
            y = 72
            if page_idx == 0:
                page.insert_text((72, y), cis_header)
                y = 118
            base = page_idx * 64
            for i in range(64):
                line_no = base + i
                page.insert_text(
                    (72, y),
                    (
                        f"CIS schedule illustration {line_no:04d}: sum assured corridor, "
                        f"premium modal yearly, nominee as per proposal, policy term."
                    ),
                )
                y += 11
                if y > 740:
                    break
            page_idx += 1
            raw = doc.tobytes()
            if len(raw) >= min_bytes:
                return raw
            if page_idx > 30:
                raise RuntimeError("mini_borderline_life_pdf: could not reach min_bytes")
    finally:
        doc.close()


def accept_shape_life_pdf() -> bytes:
    """Dense CIS-like wording; preflight expects accept (score >= 55)."""
    body = """CUSTOMER INFORMATION SHEET (CIS)
IRDAI registered product
UIN: 123LG001V01
HDFC Life Insurance Company Limited
Sum Assured Rs. 50,00,000
Death Benefit Rs. 50,00,000
Policy Term 25 years
Premium Payment Term 20 years
Modal Premium Rs. 12,000 yearly
Nominee as per proposal form
Free look period 15 days
Critical illness Rider
Section 80C Section 10(10D)
Policy Number: POL12345678901"""
    return sized_text_pdf(body, min_bytes=MIN_PAYLOAD_BYTES_DEFAULT)


def strong_vocab_life_pdf() -> bytes:
    """All major positive buckets filled — score near practical maximum (~75+)."""
    body = """CUSTOMER INFORMATION SHEET ( CIS )
HDFC Life Insurance Company Limited
IRDAI registered UIN: 123LG001V012345678
Lic Sbi Life Tata AIA Life Bajaj Allianz Life Kotak Mahindra Life Max Life
Sum Assured ₹ 50,00,000 death benefit ₹ 50,00,000 inr lakh
Policy Certificate No.: ABC123456789012
Policy Term 25 years Premium Payment Term 22 PPT
Modal Premium ₹ 12,000 yearly annual premium ₹ 24,000
Nominee appointed Free look period 30 days
Accident Rider benefit Section 80C Section 10(10D)
policy insurance premium frequency annual mode
policy bond maturity benefit survivor"""
    return sized_text_pdf(body, min_bytes=MIN_PAYLOAD_BYTES_DEFAULT)


def borderline_band_life_pdf() -> bytes:
    """Delegates to mini generator (known borderline outcome in regression runs)."""
    return mini_borderline_life_pdf()


def resume_pdf() -> bytes:
    body = """resume alex developer curriculum vitae
email example@corp.com agile scrum backlog
skills kubernetes aws github actions"""
    return sized_text_pdf(body)


def bank_statement_pdf() -> bytes:
    body = """bank statement for savings account ending 8899
statement period january 2026 transaction history deposits
opening balance credits debits closing balance narration"""
    return sized_text_pdf(body)


def invoice_pdf_no_guards_head() -> bytes:
    """Invoice wording in scan head — no policy/insurance/premium substring early."""
    body = """invoice inv-884422 billed to acme widgets pvt ltd
tax dated 2026-02-01 line items qty rate amount gst tally
duedate net payable ref serial inv-884422"""
    return sized_text_pdf(body)


def blank_pages_no_text_pdf() -> bytes:
    """No insert_text — empty pages yield < MIN_TEXT_CHARS from scan → skipped outcome."""
    import fitz

    doc = fitz.open()
    try:
        # 70 empty pages ⇒ ~11.8 KiB payload (clears structural min file size guard).
        for _ in range(70):
            doc.new_page()
        return doc.tobytes()
    finally:
        doc.close()


def structural_too_small_bytes() -> bytes:
    """Magic valid, length strictly below ``MIN_FILE_BYTES`` (never opened)."""
    from services.life.preflight import MIN_FILE_BYTES, PDF_MAGIC

    pad_len = MIN_FILE_BYTES - 1 - len(PDF_MAGIC)
    if pad_len < 1:
        raise RuntimeError("structural_too_small_bytes: MIN_FILE_BYTES too tiny")
    return PDF_MAGIC + (b"." * pad_len)


def oversized_page_count_pdf(*, pages: int = 200) -> bytes:
    import fitz

    doc = fitz.open()
    try:
        for _ in range(pages):
            doc.new_page()
        return doc.tobytes()
    finally:
        doc.close()


def invalid_magic_bytes_payload() -> bytes:
    """No ``%PDF-`` header; oversized so we do not confuse with tiny-PDF branches."""
    return b"NOT_A_PDF_PREFIX" + (b"z" * 12000)


def eighty_page_accept_life_pdf() -> bytes:
    """Perf harness: CIS text on page 1, many blanks — scanned pages capped at five."""
    import fitz

    body = """CUSTOMER INFORMATION SHEET (CIS)
IRDAI registered product
UIN: 123LG001V01
HDFC Life Insurance Company Limited
Sum Assured Rs. 50,00,000
Death Benefit Rs. 50,00,000
Policy Term 25 years
Premium Payment Term 20 years
Modal Premium Rs. 12,000 yearly
Nominee as per proposal form
Free look period 15 days
Critical illness Rider
Section 80C Section 10(10D)
Policy Number: POL12345678901"""
    doc = fitz.open()
    try:
        p0 = doc.new_page()
        y = 72
        for line in body.split("\n"):
            p0.insert_text((72, y), line)
            y += 14
        while doc.page_count < 80:
            doc.new_page()
        return doc.tobytes()
    finally:
        doc.close()


def encrypted_minimal_life_pdf(user_pw: str = "secret-upload-test") -> bytes:
    """Password-protected PDF that passes CIS size heuristic when paired with broker."""
    import fitz

    base = sized_text_pdf(
        "Sum assured statement page one\nLIC illustrative schedule row",
        min_bytes=MIN_PAYLOAD_BYTES_DEFAULT,
    )
    doc = fitz.open(stream=base, filetype="pdf")
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=user_pw)
        doc.close()
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)
