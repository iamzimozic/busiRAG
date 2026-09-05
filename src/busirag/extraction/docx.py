from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P

from busirag.schemas import (
    DOCXDocument,
    DOCXParagraph,
    DOCXTable,
)


def extract_docx(path: Path) -> DOCXDocument:
    document = Document(path)

    elements = []

    for element in document.element.body:

        if isinstance(element, CT_P):
            paragraph = Paragraph(element, document)

            if paragraph.text.strip():
                elements.append(
                    DOCXParagraph(
                        text=paragraph.text
                    )
                )

        elif isinstance(element, CT_Tbl):
            table = Table(element, document)

            rows = []

            for row in table.rows:
                rows.append(
                    [cell.text.strip() for cell in row.cells]
                )

            elements.append(
                DOCXTable(
                    rows=rows
                )
            )

    return DOCXDocument(elements=elements)