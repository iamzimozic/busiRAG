from pathlib import Path

from busirag.parser import parse_document


path = Path(
    "data/raw/apple/2023/apple-2023.pdf"
)

document = parse_document(
    path,
    company="apple",
    year=2023,
)

print(
    f"TOTAL ELEMENTS: {len(document.elements)}"
)

for index, element in enumerate(
    document.elements,
    start=1,
):
    print(
        f"\nELEMENT {index}"
    )

    print(
        f"TYPE: {type(element).__name__}"
    )

    print(
        f"PROVENANCE: {element.provenance}"
    )

    if hasattr(element, "rows"):
        print(
            f"ROWS: {len(element.rows)}"
        )

        for row in element.rows[:5]:
            print(row)

    else:
        print(
            f"TEXT: {element.text[:200]}"
        )