from pathlib import Path

from busirag.extraction.pdf import extract_pdf
from busirag.extraction.normalize import normalize_pdf
from busirag.schemas import TextElement


path = Path("data/raw/apple/2023/apple-2023.pdf")

raw_document = extract_pdf(path)

document = normalize_pdf(
    raw_document,
    source_path=path,
    company="apple",
    year=2023,
)

print("Company:", document.metadata.company)
print("Year:", document.metadata.year)
print("Filename:", document.metadata.filename)
print("Elements:", len(document.elements))

print("\nFIRST 3 ELEMENTS")

for i, element in enumerate(document.elements[:3]):
    print(
        i,
        "TEXT:",
        repr(element.text[:200]),
        "| provenance:",
        element.provenance,
    )