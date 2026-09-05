from pathlib import Path

import pdfplumber


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


STRATEGIES = [
    "lines",
    "lines_strict",
    "text",
]


def inspect_table(
    name: str,
    path: Path,
    page_number: int,
    strategy: str,
) -> None:
    print("=" * 100)
    print(f"{name} | STRATEGY: {strategy}")
    print(f"FILE: {path}")
    print(f"PAGE: {page_number}")
    print("=" * 100)

    settings = {
        "vertical_strategy": strategy,
        "horizontal_strategy": strategy,
    }

    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_number - 1]

        tables = page.find_tables(table_settings=settings)

        print(f"TABLES FOUND: {len(tables)}")
        print()

        for index, table in enumerate(tables, start=1):
            extracted = table.extract()

            print(f"--- TABLE {index} ---")
            print(f"BBOX: {table.bbox}")
            print(f"ROWS: {len(extracted)}")
            print(
                f"COLS: "
                f"{max(len(row) for row in extracted) if extracted else 0}"
            )
            print()

            for row in extracted:
                print(row)

            print()


def main() -> None:
    for name, path, page_number in PDFS:
        for strategy in STRATEGIES:
            inspect_table(
                name=name,
                path=path,
                page_number=page_number,
                strategy=strategy,
            )


if __name__ == "__main__":
    main()