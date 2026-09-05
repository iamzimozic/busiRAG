from pathlib import Path

import pymupdf

from busirag.schemas import PDFBlock, PDFDocument, PDFPage, Word


def extract_pdf(path: Path) -> PDFDocument:
    document = pymupdf.open(path)

    pages = []

    try:
        for page_number, pdf_page in enumerate(
            document,
            start=1,
        ):
            words = []

            for word in pdf_page.get_text("words"):
                x0, y0, x1, y1, text, *_ = word

                words.append(
                    Word(
                        text=text,
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                    )
                )

            tables = pdf_page.find_tables()

            table_bboxes = [
                tuple(table.bbox)
                for table in tables.tables
            ]

            blocks = []

            for block in pdf_page.get_text("blocks"):
                x0, y0, x1, y1, text, *_ = block

                text = text.strip()

                if not text:
                    continue

                blocks.append(
                    PDFBlock(
                        text=text,
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                    )
                )

            pages.append(
                PDFPage(
                    page_number=page_number,
                    width=pdf_page.rect.width,
                    height=pdf_page.rect.height,
                    words=words,
                    blocks=blocks,
                    table_bboxes=table_bboxes,
                )
            )

    finally:
        document.close()

    return PDFDocument(pages=pages)