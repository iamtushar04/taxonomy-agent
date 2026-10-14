"""
doc_parser.py — Extract raw text from uploaded product documents.

Supports: PDF, DOCX, plain text (.txt), and raw string input.
Mirrors the utility pattern in taxonomy_builder/utils/.
"""

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from an uploaded file.

    Args:
        file_bytes: Raw bytes of the uploaded file
        filename: Original filename (used to determine file type)

    Returns:
        Extracted plain text string
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return _extract_from_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        return _extract_from_docx(file_bytes)
    elif ext in (".txt", ".md"):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        # Try plain text as fallback
        try:
            return file_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"[doc_parser] Could not decode file {filename}: {e}")
            return ""


def _extract_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber (preferred) or pypdf fallback."""
    text_parts = []

    # Try pdfplumber first (better text extraction)
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        if text_parts:
            logger.info(f"[doc_parser] Extracted {len(text_parts)} pages via pdfplumber")
            return "\n\n".join(text_parts)
    except ImportError:
        logger.info("[doc_parser] pdfplumber not available, trying pypdf")
    except Exception as e:
        logger.warning(f"[doc_parser] pdfplumber failed: {e}, trying pypdf")

    # Fallback to pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        if text_parts:
            logger.info(f"[doc_parser] Extracted {len(text_parts)} pages via pypdf")
            return "\n\n".join(text_parts)
    except ImportError:
        logger.warning("[doc_parser] pypdf not available either")
    except Exception as e:
        logger.warning(f"[doc_parser] pypdf failed: {e}")

    return ""


def _extract_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        logger.info(f"[doc_parser] Extracted {len(paragraphs)} paragraphs from DOCX")
        return "\n\n".join(paragraphs)
    except ImportError:
        logger.warning("[doc_parser] python-docx not available")
        return ""
    except Exception as e:
        logger.warning(f"[doc_parser] DOCX extraction failed: {e}")
        return ""


def clean_text(text: str, max_chars: int = 10000) -> str:
    """
    Clean and truncate extracted text for LLM consumption.

    Args:
        text: Raw extracted text
        max_chars: Maximum characters to keep (default 10000)

    Returns:
        Cleaned, truncated text
    """
    if not text:
        return ""

    # Remove excessive whitespace
    import re
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    text = text.strip()

    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[... document truncated at {max_chars} characters ...]"

    return text
