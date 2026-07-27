"""
functions/tools/docx_parser.py — Tool for extracting text from DOCX files.
"""
from loguru import logger
import io
import docx

def parse_docx_bytes(docx_bytes: bytes) -> str:
    """Extracts text from DOCX bytes."""
    try:
        doc = docx.Document(io.BytesIO(docx_bytes))
        text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to parse DOCX: {e}")
        return ""
