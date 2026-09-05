from pathlib import Path

from busirag.schemas import ParsedDocument

from .docx import extract_docx
from .pdf import extract_pdf


def extract_document(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_pdf(path)

    if suffix == ".docx":
        return extract_docx(path)

    raise ValueError(f"Unsupported file format: {suffix}")