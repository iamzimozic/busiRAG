"""
Real-provider end-to-end check. Calls the Gemini API and needs an
ingested corpus (Apple 2023 10-K in tenant 1). Run with:

    pytest -m integration tests/test_answer_evaluation_integration.py
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from busirag.answer_evaluation import evaluate_answer, load_answer_cases

load_dotenv()

CASE_IDS = {
    "apple_net_income_2023",
    "unanswerable_tesla_revenue_2024",
}


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not configured",
)
def test_real_provider_answers_and_refuses():
    from busirag.db.session import SessionLocal
    from busirag.embeddings import LocalEmbeddingProvider
    from busirag.generation.gemini import GeminiProvider
    from busirag.generation.service import GenerationService
    from busirag.rag.service import RAGService
    from busirag.reranking import LocalReranker
    from busirag.versioning import CHUNKING_VERSION, EMBEDDING_MODEL

    cases = [
        case
        for case in load_answer_cases(
            Path("data/evaluation/answers.json")
        )
        if case.id in CASE_IDS
    ]

    service = RAGService(
        embedding_provider=LocalEmbeddingProvider(),
        reranker=LocalReranker(),
        generation_service=GenerationService(GeminiProvider()),
        cache=None,
        chunking_version=CHUNKING_VERSION,
        embedding_model=EMBEDDING_MODEL,
    )

    checks = {}

    with SessionLocal() as session:
        for case in cases:
            result = service.query(
                session=session,
                query=case.query,
                tenant_id=1,
            )

            checks[case.id] = evaluate_answer(
                case,
                result.answer,
                result.sources,
            )

    assert checks["apple_net_income_2023"].numeric_result == "correct"
    assert checks["unanswerable_tesla_revenue_2024"].refused
