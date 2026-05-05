"""Extract plain text from PDF bytes using PyMuPDF, with optional OCR for scanned pages."""

from __future__ import annotations

import logging

logger = logging.getLogger("kavach.life.pdf")

# Minimum characters before we assume text layer is usable (whole document).
MIN_TEXT_CHARS_FOR_SKIP_OCR = 200
# Per-page: if below this, try OCR for that page (when tesseract available).
MIN_CHARS_PER_PAGE_OCR = 40


def _ocr_page_png(page: object) -> str:
    """OCR a single page pixmap via pytesseract. Requires Tesseract binary + pytesseract."""
    try:
        import io

        import fitz
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.warning("life.pdf.ocr_missing deps=pytesseract|Pillow")
        raise RuntimeError("ocr_dependencies_missing") from None

    mat = fitz.Matrix(2.0, 2.0)
    pm = page.get_pixmap(matrix=mat, alpha=False)  # type: ignore[union-attr]
    img = Image.open(io.BytesIO(pm.tobytes("png")))
    text = pytesseract.image_to_string(img, lang="eng")
    return text or ""


def pdf_bytes_to_text_maybe_ocr(pdf_bytes: bytes, filename: str = "upload.pdf", *, use_ocr: bool = True) -> str:
    """Extract text; run OCR on sparse pages when ``use_ocr`` and tesseract are available."""
    try:
        import fitz  # pymupdf
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pymupdf (fitz) is required for PDF text extraction") from e

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        parts: list[str] = []
        for page in doc:
            raw = page.get_text("text") or ""
            if (
                use_ocr
                and len(raw.strip()) < MIN_CHARS_PER_PAGE_OCR
            ):
                try:
                    ocr = _ocr_page_png(page)
                    if len(ocr.strip()) > len(raw.strip()):
                        raw = ocr
                        logger.info("life.pdf.ocr_used page=%s file=%s", page.number + 1, filename)
                except RuntimeError:
                    pass  # deps missing — keep text layer
                except Exception as e:  # pragma: no cover
                    logger.warning("life.pdf.ocr_failed page=%s err=%s", page.number + 1, e)
            parts.append(raw)
        merged = "\n".join(parts)
        # Whole-doc fallback: almost empty → try full OCR page-by-page if anything failed hard
        if use_ocr and len(merged.strip()) < MIN_TEXT_CHARS_FOR_SKIP_OCR:
            try:
                ocr_parts: list[str] = []
                for page in doc:
                    ocr_parts.append(_ocr_page_png(page))
                ocr_merged = "\n".join(ocr_parts)
                if len(ocr_merged.strip()) > len(merged.strip()):
                    merged = ocr_merged
                    logger.info("life.pdf.full_ocr_fallback file=%s", filename)
            except Exception:
                pass
        return merged
    finally:
        doc.close()


def pdf_bytes_to_text(pdf_bytes: bytes, filename: str = "upload.pdf") -> str:
    """Extract text from PDF; uses OCR when the text layer is sparse (scanned docs)."""
    return pdf_bytes_to_text_maybe_ocr(pdf_bytes, filename=filename, use_ocr=True)
