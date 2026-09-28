import argparse
from pathlib import Path

from busirag.embeddings import LocalEmbeddingProvider
from busirag.ingestion import ingest_document


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest every PDF/DOCX under <root>/<company>/<year>/."
        )
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/raw"),
    )

    parser.add_argument(
        "--tenant-id",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    data_root = args.root

    provider = LocalEmbeddingProvider()

    files = sorted(
        path
        for path in data_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".pdf", ".docx"}
    )

    if not files:
        raise RuntimeError(f"No supported documents found under {data_root}")

    total_chunks = 0

    print(f"Found {len(files)} documents")

    for path in files:
        relative = path.relative_to(data_root)
        parts = relative.parts

        if len(parts) < 3:
            print(f"Skipping unexpected path: {path}")
            continue

        company = parts[0]

        try:
            year = int(parts[1])
        except ValueError:
            print(f"Skipping document with invalid year: {path}")
            continue

        print()
        print("=" * 70)
        print(f"Ingesting: {relative}")
        print(f"Company: {company}")
        print(f"Year: {year}")
        print("=" * 70)

        chunks = ingest_document(
            path=path,
            company=company,
            year=year,
            embedding_provider=provider,
            tenant_id=args.tenant_id,
            original_filename=path.name,
        )

        total_chunks += chunks

    print()
    print("=" * 70)
    print(f"Corpus ingestion complete")
    print(f"Documents discovered: {len(files)}")
    print(f"New chunks inserted: {total_chunks}")
    print("=" * 70)


if __name__ == "__main__":
    main()