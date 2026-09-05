from pathlib import Path

from busirag.extraction.router import extract_document


DATA_DIR = Path("data/raw")


def main():
    for path in sorted(DATA_DIR.rglob("*")):
        if not path.is_file():
            continue

        print("=" * 80)
        print("FILE:", path)

        try:
            document = extract_document(path)

            total_words = sum(
                len(page.words)
                for page in document.pages
            )

            print("Pages:", len(document.pages))
            print("Words:", total_words)
            print("Status: OK")

        except Exception as e:
            print("Status: FAILED")
            print("Error:", e)


if __name__ == "__main__":
    main()