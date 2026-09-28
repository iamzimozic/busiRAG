import os
import urllib.request

import pytest

from busirag.generation.ollama import OllamaProvider
from busirag.generation.service import GenerationService
from busirag.retrieval.vector import RetrievalResult

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434/v1",
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


def ollama_available() -> bool:
    try:
        urllib.request.urlopen(
            OLLAMA_BASE_URL.removesuffix("/v1") + "/api/tags",
            timeout=2,
        )
    except OSError:
        return False

    return True


@pytest.mark.integration
@pytest.mark.skipif(
    not ollama_available(),
    reason="Ollama server not reachable",
)
def test_ollama_provider_answers_with_citations():
    service = GenerationService(
        OllamaProvider(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
    )

    result = service.generate(
        "What was Apple's net income in 2023?",
        [
            RetrievalResult(
                chunk_id=435,
                document_id=1,
                text=(
                    "(In millions) Net income $ 96,995 $ 99,803 "
                    "$ 94,680 for 2023, 2022 and 2021"
                ),
                company="apple",
                filename="apple-2023.pdf",
                year=2023,
                page_number=32,
                section=None,
                element_type="table",
                similarity=0.9,
            )
        ],
    )

    assert "96,995" in result.answer
    assert [source.citation_id for source in result.sources] == ["S1"]
