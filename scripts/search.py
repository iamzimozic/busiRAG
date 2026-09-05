import argparse

from busirag.db.session import SessionLocal
from busirag.embeddings import LocalEmbeddingProvider
from busirag.retrieval import retrieve_similar_chunks


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "query",
        type=str,
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    provider = LocalEmbeddingProvider()

    with SessionLocal() as session:
        results = retrieve_similar_chunks(
            session=session,
            query=args.query,
            embedding_provider=provider,
            top_k=args.top_k,
        )

    print("=" * 110)
    print("VECTOR SEARCH")
    print("=" * 110)

    print(f"Query: {args.query}")
    print(f"Results: {len(results)}")

    for rank, result in enumerate(results, start=1):
        print("\n" + "-" * 110)
        print(f"RESULT {rank}")
        print("-" * 110)

        print(f"Similarity: {result.similarity:.4f}")
        print(f"Chunk ID:   {result.chunk_id}")
        print(f"Document:   {result.document_id}")
        print(f"Company:    {result.company}")
        print(f"Year:       {result.year}")
        print(f"Page:       {result.page_number}")
        print(f"Type:       {result.element_type}")
        print(f"Section:    {result.section!r}")

        print("\nTEXT:")
        print(result.text[:3000])


if __name__ == "__main__":
    main()