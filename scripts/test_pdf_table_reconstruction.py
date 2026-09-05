from pathlib import Path

from busirag.extraction.layout import group_words_into_rows
from busirag.extraction.pdf import extract_pdf
from busirag.extraction.pdf_tables import get_words_in_table
from busirag.extraction.tables import (
    classify_numeric_columns,
    cluster_numeric_columns,
    reconstruct_table_region,
)


RAW_DIR = Path("data/raw")


def inspect_document(
    path: Path,
    page_number: int,
) -> None:
    print(f"\n{'=' * 80}")
    print(path)
    print(f"PAGE {page_number}")
    print("=" * 80)

    document = extract_pdf(path)
    page = document.pages[page_number - 1]

    if not page.table_bboxes:
        print("NO TABLE FOUND")
        return

    for table_index, bbox in enumerate(page.table_bboxes):
        print(f"\nTABLE {table_index}")
        print(f"BBOX: {bbox}")

        words = get_words_in_table(
            page=page,
            bbox=bbox,
        )

        rows = group_words_into_rows(words)

        columns = cluster_numeric_columns(rows)
        roles = classify_numeric_columns(rows, columns)

        print("\nCOLUMNS")

        for column, role in zip(columns, roles):
            print(
                f"  x={column:.2f} -> {role}"
            )

        reconstructed = reconstruct_table_region(
            rows,
        )

        print("\nRECONSTRUCTED ROWS")

        for index, row in enumerate(reconstructed, start=1):
            print(f"{index:03}: {row}")


inspect_document(
    RAW_DIR / "nvidia/2025/nvidia-2025.pdf",
    71,
)