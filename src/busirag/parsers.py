from pathlib import Path

import pymupdf

from .schemas import Page, ParsedDocument


def parse_pdf(path: Path) -> ParsedDocument:
    document = pymupdf.open(path)

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text()

        pages.append(
            Page(
                page_number=page_number,
                text=text,
            )
        )

    document.close()

    return ParsedDocument(pages=pages)