from pathlib import Path

from sqlalchemy import select

from busirag.chunking import chunk_document
from busirag.db.models import Chunk as ChunkModel
from busirag.db.models import Document as DocumentModel
from busirag.db.session import SessionLocal
from busirag.embeddings import EmbeddingProvider
from busirag.hashing import hash_file, hash_text
from busirag.parser import parse_document

from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL

EMBEDDING_BATCH_SIZE = 32


def ingest_document(
    path: Path,
    company: str,
    year: int,
    embedding_provider: EmbeddingProvider,
) -> int:
    """
    Parse, chunk, embed and store a document.

    Returns the number of chunks inserted.
    """

    path = path.resolve()

    if not path.exists():
        raise FileNotFoundError(path)

    document_hash = hash_file(path)

    with SessionLocal() as session:

        existing_document = session.scalar(
            select(DocumentModel).where(
                DocumentModel.content_hash == document_hash,
                DocumentModel.chunking_version == CHUNKING_VERSION,
                DocumentModel.embedding_model == EMBEDDING_MODEL,
            )
        )

        if existing_document is not None:
            print(
                f"Already ingested: {path.name} "
                f"(document_id={existing_document.id})"
            )
            return 0

        print(f"Parsing: {path}")

        parsed_document = parse_document(
            path=path,
            company=company,
            year=year,
        )

        chunks = chunk_document(
            document=parsed_document,
            company=company,
            year=year,
            source_path=str(path),
        )

        if not chunks:
            raise ValueError(
                f"No chunks generated for {path}"
            )

        print(f"Generated {len(chunks)} chunks")

        document = DocumentModel(
            company=company,
            year=year,
            filename=path.name,
            source_path=str(path),
            content_hash=document_hash,
            chunking_version=CHUNKING_VERSION,
            embedding_model=EMBEDDING_MODEL,
        )

        session.add(document)
        session.flush()

        print(f"Created document id={document.id}")

        for start in range(
            0,
            len(chunks),
            EMBEDDING_BATCH_SIZE,
        ):
            batch = chunks[
                start : start + EMBEDDING_BATCH_SIZE
            ]

            texts = [chunk.text for chunk in batch]

            print(
                f"Embedding chunks "
                f"{start + 1}-{start + len(batch)} "
                f"of {len(chunks)}"
            )

            embeddings = (
                embedding_provider.embed_documents(texts)
            )

            for chunk, embedding in zip(
                batch,
                embeddings,
            ):
                session.add(
                    ChunkModel(
                        document_id=document.id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        element_type=chunk.element_type,
                        section=chunk.section,
                        page_number=chunk.page_number,
                        token_count=chunk.token_count,
                        content_hash=hash_text(chunk.text),
                        embedding=embedding,
                        chunking_version=CHUNKING_VERSION,
                        embedding_model=EMBEDDING_MODEL,
                    )
                )

        session.commit()

        print(
            f"Ingestion complete: "
            f"{len(chunks)} chunks"
        )

        return len(chunks)