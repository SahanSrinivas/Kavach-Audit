"""Extract plain text from PDF bytes using PyMuPDF."""

from __future__ import annotations


def pdf_bytes_to_text(pdf_bytes: bytes, filename: str = "upload.pdf") -> str:
    try:
        import fitz  # pymupdf
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pymupdf (fitz) is required for PDF text extraction") from e

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        parts: list[str] = []
        for page in doc:
            parts.append(page.get_text("text"))
        return "\n".join(parts)
    finally:
        doc.close()
