from pathlib import Path

from busirag.parser import parse_document


documents = [
    (
        Path("data/raw/apple/2023/apple-2023.pdf"),
        "apple",
        2023,
    ),
    (
        Path("data/raw/microsoft/2023/microsoft-2023.docx"),
        "microsoft",
        2023,
    ),
]


for path, company, year in documents:

    document = parse_document(
        path,
        company=company,
        year=year,
    )

    print("=" * 80)
    print("FILE:", path)
    print("COMPANY:", document.metadata.company)
    print("YEAR:", document.metadata.year)
    print("ELEMENTS:", len(document.elements))

    for element in document.elements[:3]:
        print(type(element).__name__)