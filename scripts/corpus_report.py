from pathlib import Path

from busirag.ingestion import discover_documents
from busirag.parser import parse_document
from busirag.schemas import TableElement, TextElement


documents = discover_documents(Path("data/raw"))

print("=" * 100)
print("CORPUS QUALITY REPORT")
print("=" * 100)

for source in documents:
    parsed = parse_document(
        source.path,
        company=source.company,
        year=source.year,
    )

    text_elements = [
        element
        for element in parsed.elements
        if isinstance(element, TextElement)
    ]

    table_elements = [
        element
        for element in parsed.elements
        if isinstance(element, TableElement)
    ]

    total_characters = sum(
        len(element.text)
        for element in text_elements
    )

    print()
    print(f"{source.company.upper()} {source.year}")
    print(f"  File:             {source.path.name}")
    print(f"  Format:           {source.format}")
    print(f"  Total elements:   {len(parsed.elements)}")
    print(f"  Text elements:    {len(text_elements)}")
    print(f"  Table elements:   {len(table_elements)}")
    print(f"  Characters:       {total_characters:,}")