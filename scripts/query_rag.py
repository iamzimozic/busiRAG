from busirag.db.session import SessionLocal
from busirag.embeddings.local import LocalEmbeddingProvider
from busirag.generation.gemini import GeminiProvider
from busirag.generation.service import GenerationService
from busirag.rag.service import RAGService
from busirag.reranking.local import LocalReranker
from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL


def main() -> None:
    embedding_provider = LocalEmbeddingProvider()

    reranker = LocalReranker(
        model_name="BAAI/bge-reranker-v2-m3",
    )

    llm = GeminiProvider(
        model="gemini-2.5-flash",
    )

    generation_service = GenerationService(llm)

    rag_service = RAGService(
        embedding_provider=embedding_provider,
        reranker=reranker,
        generation_service=generation_service,
        chunking_version=CHUNKING_VERSION,
        embedding_model=EMBEDDING_MODEL,
        candidate_k=50,
        top_k=10,
    )

    query = "What was Apple's net income in 2023?"

    with SessionLocal() as session:
        response = rag_service.query(
            session=session,
            query=query,
        )

    print("\n" + "=" * 80)
    print("QUERY")
    print("=" * 80)
    print(query)

    print("\n" + "=" * 80)
    print("ANSWER")
    print("=" * 80)
    print(response.answer)

    print("\n" + "=" * 80)
    print("SOURCES")
    print("=" * 80)

    for source in response.sources:
        print(
            f"[{source.citation_id}] "
            f"{source.company} {source.year} | "
            f"Page {source.page_number} | "
            f"Chunk {source.chunk_id}"
        )


if __name__ == "__main__":
    main()