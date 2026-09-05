from pathlib import Path

from busirag.extraction.docx import extract_docx
from busirag.extraction.normalize import normalize_docx
from busirag.schemas import TableElement, TextElement


path = Path("data/raw/microsoft/2023/microsoft-2023.docx")

raw_document = extract_docx(path)

document = normalize_docx(
    raw_document,
    source_path=path,
    company="microsoft",
    year=2023,
)

print("Company:", document.metadata.company)
print("Year:", document.metadata.year)
print("Filename:", document.metadata.filename)
print("Elements:", len(document.elements))

print("\nFIRST 10 ELEMENTS")

for i, element in enumerate(document.elements[:10]):
    if isinstance(element, TextElement):
        print(
            i,
            "TEXT:",
            repr(element.text[:80]),
            "| provenance:",
            element.provenance,
        )

    elif isinstance(element, TableElement):
        print(
            i,
            "TABLE:",
            len(element.rows),
            "rows",
            "| provenance:",
            element.provenance,
        )