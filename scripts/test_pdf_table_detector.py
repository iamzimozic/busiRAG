from pathlib import Path

from busirag.extraction.pdf import extract_pdf
from busirag.extraction.pdf_tables import get_words_in_table


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
        print(f"PAGE: {page_number}")
        print("=" * 100)

        pdf_document = extract_pdf(path)
        page = pdf_document.pages[page_number - 1]

        tables = page.table_bboxes

        print(f"TABLES FOUND: {len(tables)}")

        for index, bbox in enumerate(tables, start=1):
            words = get_words_in_table(
                page=page,
                bbox=bbox,
            )

            print()
            print(f"TABLE {index}")
            print(f"BBOX: {bbox}")
            print(f"WORDS: {len(words)}")
            print()

            for word in words:
                print(
                    f"{word.text:30} "
                    f"x0={word.x0:7.1f} "
                    f"x1={word.x1:7.1f} "
                    f"y0={word.y0:7.1f} "
                    f"y1={word.y1:7.1f}"
                )


if __name__ == "__main__":
    main()