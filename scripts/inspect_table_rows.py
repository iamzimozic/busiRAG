from pathlib import Path

from busirag.extraction.pdf import extract_pdf
from busirag.extraction.pdf_tables import detect_pdf_tables
from busirag.extraction.table_regions import (
    inspect_table_rows,
    find_data_rows,
    find_recurring_numeric_columns,
    find_region_boundaries,
    row_signature,
    get_region_rows,
    assign_words_to_columns,
    get_region_rows,
)


PDFS = [
    (
        "Apple 2023",
        Path("data/raw/apple/2023/apple-2023.pdf"),
        31,
    ),
    (
        "NVIDIA 2025",
        Path("data/raw/nvidia/2025/nvidia-2025.pdf"),
        71,
    ),
]


def main() -> None:
    for name, path, page_number in PDFS:
        print("=" * 100)
        print(name)
        print("=" * 100)

        document = extract_pdf(path)
        page = document.pages[page_number - 1]

        tables = detect_pdf_tables(
            path=path,
            page_number=page_number,
        )

        for table_index, bbox in enumerate(tables, start=1):
            rows = inspect_table_rows(
                page=page,
                bbox=bbox,
            )

            # ---------------------------------------------------------
            # Discover recurring numeric columns
            # ---------------------------------------------------------
            columns = find_recurring_numeric_columns(rows)

            print("\nRECURRING NUMERIC COLUMNS")
            print(
                " ".join(
                    f"{column:.1f}"
                    for column in columns
                )
            )

            # ---------------------------------------------------------
            # Identify rows participating in the table structure
            # ---------------------------------------------------------
            data_rows = find_data_rows(
                rows,
                columns,
            )

            print("\nDATA ROWS")
            print(data_rows)

            # ---------------------------------------------------------
            # Determine the broader table region
            # ---------------------------------------------------------
            region = find_region_boundaries(
                rows,
                data_rows,
            )

            print("\nTABLE REGION")

            if region is None:
                print(None)
            else:
                start, end = region
                print(f"rows {start + 1} → {end + 1}")

            if region is not None:
                table_rows = get_region_rows(
                    rows,
                    region,
                )

                print("\nRECONSTRUCTED VISUAL ROWS")

                for index, row in enumerate(
                    table_rows,
                    start=1,
                ):
                    reconstructed = assign_words_to_columns(
                        row,
                        columns,
                    )

                    print(
                        f"{index:03d}: "
                        f"{reconstructed}"
                    )

            # ---------------------------------------------------------
            # Show row signatures
            # ---------------------------------------------------------
            print("\nROW SIGNATURES")

            for index, row in enumerate(rows, start=1):
                signature = row_signature(
                    row,
                    columns,
                )

                if signature:
                    text = " ".join(
                        word.text
                        for word in row
                    )

                    print(
                        f"{index:03d}: "
                        f"{signature} | "
                        f"{text}"
                    )

            print("\n" + "-" * 100)
            print(
                f"TABLE {table_index} | "
                f"ROWS: {len(rows)} | "
                f"BBOX: {bbox}"
            )
            print("-" * 100)


if __name__ == "__main__":
    main()