"""
Provider contract tests: every generation provider must turn the same
prompts into the same GeneratedAnswer, so GenerationService produces
identical answers and citations whichever provider is configured.

The LangChain chat model classes are replaced with fakes; no network
calls are made.
"""

import json

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

import busirag.generation.gemini as gemini_module
import busirag.generation.ollama as ollama_module
import busirag.generation.openai as openai_module
from busirag.config import Settings
from busirag.errors import GenerationError
from busirag.generation.factory import (
    create_llm_provider,
    llm_identity,
)
from busirag.generation.gemini import GeminiProvider
from busirag.generation.mock import ScriptedLLMProvider
from busirag.generation.ollama import OllamaProvider
from busirag.generation.openai import OpenAIProvider
from busirag.generation.response import GeneratedAnswer
from busirag.generation.service import GenerationService
from busirag.retrieval.vector import RetrievalResult

ANSWER = "Apple's net income in 2023 was $96,995 million."
CITATIONS = ["S1"]


class FakeStructuredRunnable:
    def __init__(self, schema, calls):
        self.schema = schema
        self.calls = calls

    def invoke(self, messages):
        self.calls.append(messages)
        return self.schema(answer=ANSWER, citations=CITATIONS)


class FakeStructuredChatModel:
    """Stands in for ChatGoogleGenerativeAI / ChatOpenAI structured output."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.schema = None
        FakeStructuredChatModel.instances.append(self)

    def with_structured_output(self, schema):
        self.schema = schema
        return FakeStructuredRunnable(schema, self.calls)


class FakeJsonChatModel:
    """Stands in for ChatOpenAI pointed at Ollama in JSON mode."""

    instances = []
    reply = json.dumps({"answer": ANSWER, "citations": CITATIONS})

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.bound = {}
        self.calls = []
        FakeJsonChatModel.instances.append(self)

    def bind(self, **kwargs):
        self.bound = kwargs
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.reply)


@pytest.fixture(autouse=True)
def fake_chat_models(monkeypatch):
    # Settings also reads the process environment (.env is loaded by
    # busirag.db.session), so clear provider variables for isolation.
    for name in (
        "LLM_PROVIDER",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
        "OLLAMA_MODEL",
        "OLLAMA_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    FakeStructuredChatModel.instances = []
    FakeJsonChatModel.instances = []
    FakeJsonChatModel.reply = json.dumps(
        {"answer": ANSWER, "citations": CITATIONS}
    )

    monkeypatch.setattr(
        gemini_module,
        "ChatGoogleGenerativeAI",
        FakeStructuredChatModel,
    )
    monkeypatch.setattr(
        openai_module,
        "ChatOpenAI",
        FakeStructuredChatModel,
    )
    monkeypatch.setattr(
        ollama_module,
        "ChatOpenAI",
        FakeJsonChatModel,
    )


def build_provider(name):
    if name == "gemini":
        return GeminiProvider(model="gemini-test", api_key="key")

    if name == "openai":
        return OpenAIProvider(model="gpt-test", api_key="key")

    return OllamaProvider(model="local-test")


def last_messages(name):
    model_class = (
        FakeJsonChatModel if name == "ollama" else FakeStructuredChatModel
    )

    return model_class.instances[-1].calls[-1]


RETRIEVED = [
    RetrievalResult(
        chunk_id=435,
        document_id=1,
        text="Net income $ 96,995 $ 99,803",
        company="apple",
        filename="apple-2023.pdf",
        year=2023,
        page_number=32,
        section=None,
        element_type="table",
        similarity=0.9,
    ),
    RetrievalResult(
        chunk_id=436,
        document_id=1,
        text="Total net sales $ 383,285",
        company="apple",
        filename="apple-2023.pdf",
        year=2023,
        page_number=32,
        section=None,
        element_type="table",
        similarity=0.8,
    ),
]

PROVIDERS = ["gemini", "openai", "ollama"]


@pytest.mark.parametrize("name", PROVIDERS)
def test_provider_returns_generated_answer(name):
    provider = build_provider(name)

    result = provider.generate(
        system_prompt="system rules",
        user_prompt="question and sources",
    )

    assert result == GeneratedAnswer(answer=ANSWER, citations=CITATIONS)
    assert last_messages(name) == [
        ("system", "system rules"),
        ("human", "question and sources"),
    ]


@pytest.mark.parametrize("name", PROVIDERS)
def test_generation_service_output_is_identical_across_providers(name):
    reference = GenerationService(
        ScriptedLLMProvider(
            {"": GeneratedAnswer(answer=ANSWER, citations=CITATIONS)}
        )
    ).generate("What was Apple's net income?", RETRIEVED)

    response = GenerationService(build_provider(name)).generate(
        "What was Apple's net income?",
        RETRIEVED,
    )

    assert response == reference
    assert [source.chunk_id for source in response.sources] == [435]
    assert response.sources[0].page_number == 32


def test_structured_providers_request_the_answer_schema():
    build_provider("gemini")
    build_provider("openai")

    gemini, openai = FakeStructuredChatModel.instances

    assert gemini.schema is GeneratedAnswer
    assert gemini.kwargs["model"] == "gemini-test"
    assert openai.schema is GeneratedAnswer
    assert openai.kwargs["model"] == "gpt-test"
    assert openai.kwargs["temperature"] == 0.0


def test_openai_provider_supports_compatible_endpoints():
    OpenAIProvider(
        model="gpt-test",
        api_key="key",
        base_url="https://llm.example.com/v1",
        temperature=None,
    )

    [model] = FakeStructuredChatModel.instances

    assert model.kwargs["base_url"] == "https://llm.example.com/v1"
    assert "temperature" not in model.kwargs


def test_ollama_provider_uses_openai_compatible_json_mode():
    OllamaProvider(
        model="qwen2.5:7b",
        base_url="http://ollama:11434/v1",
    )

    [model] = FakeJsonChatModel.instances

    assert model.kwargs["base_url"] == "http://ollama:11434/v1"
    assert model.kwargs["model"] == "qwen2.5:7b"
    assert model.bound == {"response_format": {"type": "json_object"}}


def test_ollama_provider_accepts_fenced_json():
    FakeJsonChatModel.reply = (
        "```json\n"
        + json.dumps({"answer": ANSWER, "citations": CITATIONS})
        + "\n```"
    )

    result = build_provider("ollama").generate("s", "u")

    assert result.answer == ANSWER


@pytest.mark.parametrize(
    "reply",
    [
        "Apple earned $96,995 million.",
        json.dumps({"answer": ANSWER}),
        json.dumps({"answer": "", "citations": []}),
    ],
)
def test_ollama_provider_rejects_malformed_output(reply):
    FakeJsonChatModel.reply = reply

    with pytest.raises(GenerationError, match="invalid answer"):
        build_provider("ollama").generate("s", "u")


@pytest.mark.parametrize("name", PROVIDERS)
def test_invalid_citations_raise_generation_error(name, monkeypatch):
    provider = build_provider(name)

    monkeypatch.setattr(
        provider,
        "generate",
        lambda **kwargs: GeneratedAnswer(answer=ANSWER, citations=["S9"]),
    )

    with pytest.raises(GenerationError, match="invalid citations"):
        GenerationService(provider).generate("q", RETRIEVED)


def test_provider_failures_become_generation_errors():
    class FailingProvider:
        def generate(self, system_prompt, user_prompt):
            raise TimeoutError("upstream timed out")

    with pytest.raises(GenerationError, match="TimeoutError"):
        GenerationService(FailingProvider()).generate("q", RETRIEVED)


def settings(**overrides):
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret_key="secret",
        **overrides,
    )


@pytest.mark.parametrize(
    ("overrides", "provider_class", "identity"),
    [
        (
            {"gemini_api_key": "key"},
            GeminiProvider,
            "gemini:gemini-2.5-flash",
        ),
        (
            {"llm_provider": "openai", "openai_api_key": "key"},
            OpenAIProvider,
            "openai:gpt-4.1-mini",
        ),
        (
            {"llm_provider": "ollama", "ollama_model": "llama3.1:8b"},
            OllamaProvider,
            "ollama:llama3.1:8b",
        ),
    ],
)
def test_factory_selects_configured_provider(
    overrides,
    provider_class,
    identity,
):
    configured = settings(**overrides)

    assert isinstance(create_llm_provider(configured), provider_class)
    assert llm_identity(configured) == identity


def test_gemini_is_the_default_provider():
    assert settings(gemini_api_key="key").llm_provider == "gemini"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({}, "GEMINI_API_KEY is required"),
        ({"llm_provider": "openai"}, "OPENAI_API_KEY is required"),
        ({"llm_provider": "anthropic"}, "llm_provider"),
    ],
)
def test_provider_settings_are_validated(overrides, message):
    with pytest.raises(ValidationError, match=message):
        settings(**overrides)


def test_ollama_needs_no_api_key():
    assert settings(llm_provider="ollama").llm_provider == "ollama"
