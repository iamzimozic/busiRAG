from pathlib import Path

from busirag.ingestion import discover_documents
from busirag.parser import parse_document


RAW_DIR = Path("data/raw")


documents = discover_documents(RAW_DIR)

print(f"DOCUMENTS FOUND: {len(documents)}")
print()

for source in documents:
    print("=" * 80)
    print(
        f"{source.company.upper()} "
        f"{source.year} "
        f"{source.path.name}"
    )
    print("=" * 80)

    document = parse_document(
        source.path,
        company=source.company,
        year=source.year,
    )

    text_elements = [
        element
        for element in document.elements
        if type(element).__name__ == "TextElement"
    ]

    table_elements = [
        element
        for element in document.elements
        if type(element).__name__ == "TableElement"
    ]

    print(f"TOTAL ELEMENTS: {len(document.elements)}")
    print(f"TEXT ELEMENTS:  {len(text_elements)}")
    print(f"TABLE ELEMENTS: {len(table_elements)}")

    table_pages = [
        element.provenance.page_number
        for element in table_elements
    ]

    print(f"TABLE PAGES:    {table_pages}")
    print()