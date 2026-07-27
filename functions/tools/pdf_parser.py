"""
functions/tools/pdf_parser.py — Tool for extracting text from PDFs.
"""
from pypdf import PdfReader
from loguru import logger
import io

def parse_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extracts text from PDF bytes."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to parse PDF: {e}")
        return ""
