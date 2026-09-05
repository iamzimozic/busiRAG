from busirag.generation.mock import MockLLMProvider
from busirag.generation.service import GenerationService


def test_generation_service():
    llm = MockLLMProvider()
    service = GenerationService(llm)

    result = service.generate(
        query="What was Apple's net income in 2023?",
        retrieval_results=[],
    )

    assert result.answer == "MOCK ANSWER"
    assert result.sources == []