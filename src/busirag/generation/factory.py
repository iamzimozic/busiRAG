from busirag.config import Settings
from busirag.errors import ConfigurationError
from busirag.generation.base import LLMProvider


def llm_model_name(settings: Settings) -> str:
    models = {
        "gemini": settings.gemini_model,
        "openai": settings.openai_model,
        "ollama": settings.ollama_model,
    }

    return models[settings.llm_provider]


def llm_identity(settings: Settings) -> str:
    """Provider and model, e.g. "gemini:gemini-2.5-flash" (used in cache keys)."""

    return f"{settings.llm_provider}:{llm_model_name(settings)}"


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Build the generation provider selected by LLM_PROVIDER."""

    if settings.llm_provider == "gemini":
        from busirag.generation.gemini import GeminiProvider

        return GeminiProvider(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key,
        )

    if settings.llm_provider == "openai":
        from busirag.generation.openai import OpenAIProvider

        return OpenAIProvider(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    if settings.llm_provider == "ollama":
        from busirag.generation.ollama import OllamaProvider

        return OllamaProvider(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )

    raise ConfigurationError(
        f"Unknown LLM provider {settings.llm_provider!r}"
    )
