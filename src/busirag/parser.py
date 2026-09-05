from pathlib import Path

from busirag.extraction.docx import extract_docx
from busirag.extraction.normalize import normalize_docx, normalize_pdf
from busirag.extraction.pdf import extract_pdf
from busirag.schemas import ParsedDocument


def parse_document(
    path: Path,
    company: str,
    year: int,
) -> ParsedDocument:

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        raw_document = extract_pdf(path)

        return normalize_pdf(
            raw_document,
            source_path=path,
            company=company,
            year=year,
        )

    if suffix == ".docx":
        raw_document = extract_docx(path)

        return normalize_docx(
            raw_document,
            source_path=path,
            company=company,
            year=year,
        )

    raise ValueError(
        f"Unsupported document format: {suffix}"
    )