import argparse
from pathlib import Path

from busirag.embeddings import LocalEmbeddingProvider
from busirag.ingestion import ingest_document


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a financial document into Busirag."
    )

    parser.add_argument(
        "path",
        type=Path,
    )

    parser.add_argument(
        "--company",
        required=True,
    )

    parser.add_argument(
        "--year",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--tenant-id",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    provider = LocalEmbeddingProvider()

    ingest_document(
        path=args.path,
        company=args.company,
        year=args.year,
        embedding_provider=provider,
        tenant_id=args.tenant_id,
        original_filename=args.path.name,
    )


if __name__ == "__main__":
    main()
