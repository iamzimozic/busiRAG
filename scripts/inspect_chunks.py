import sys

from sqlalchemy import select
from collections import defaultdict

from busirag.db.models import Chunk, Document
from busirag.db.session import SessionLocal
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  PYTHONPATH=src python scripts/inspect_chunks.py 'net income'")
        return

    query = " ".join(sys.argv[1:])

    with SessionLocal() as session:
        results = session.execute(
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(
                Chunk.chunking_version == CHUNKING_VERSION,
                Chunk.embedding_model == EMBEDDING_MODEL,
                Chunk.text.ilike(f"%{query}%"),
            )
            .order_by(
                Document.company,
                Document.year,
                Chunk.chunk_index,
            )
        ).all()

        groups = defaultdict(list)

        for chunk, document in results:
            groups[(document.company, document.year)].append(
                (chunk, document)
            )

        print()
        print("=" * 100)
        print(f"SEARCH: {query}")
        print(f"RESULTS: {len(results)}")
        print("=" * 100)

        for (company, year), items in groups.items():
            print()
            print("=" * 100)
            print(f"{company.upper()} {year} | {len(items)} matching chunks")
            print("=" * 100)

            for chunk, document in items[:5]:
                print()
                print(
                    f"CHUNK {chunk.id} | "
                    f"page={chunk.page_number} | "
                    f"type={chunk.element_type}"
                )
                print("-" * 100)
                print(
                    chunk.text
                    .replace("\n", " ")
                )


if __name__ == "__main__":
    main()