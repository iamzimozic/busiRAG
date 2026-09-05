import os

import pytest
from dotenv import load_dotenv

from busirag.generation.gemini import GeminiProvider


load_dotenv()


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not configured",
)

def test_gemini_provider():
    provider = GeminiProvider()

    result = provider.generate(
        system_prompt="You are a helpful assistant.",
        user_prompt=(
            'Return the answer "GEMINI WORKS" '
            "with no citations."
        ),
    )

    assert result.answer == "GEMINI WORKS"
    assert result.citations == []