from langchain_openai import ChatOpenAI

from busirag.errors import GenerationError
from busirag.generation.parser import parse_generated_answer
from busirag.generation.response import GeneratedAnswer


class OllamaProvider:
    """
    Local models served by Ollama through its OpenAI-compatible API.

    Small local models do not reliably support tool/JSON-schema
    structured output, so this provider requests JSON mode and parses
    the reply with the same parser used for raw LLM output. The system
    prompt already specifies the {"answer", "citations"} format.
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434/v1",
        temperature: float = 0.0,
    ):
        self.llm = ChatOpenAI(
            model=model,
            base_url=base_url,
            # Ollama ignores the key, but the OpenAI client requires one.
            api_key="ollama",
            temperature=temperature,
        ).bind(
            response_format={"type": "json_object"},
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> GeneratedAnswer:
        message = self.llm.invoke(
            [
                ("system", system_prompt),
                ("human", user_prompt),
            ]
        )

        try:
            # Citation ids are validated against the context by
            # GenerationService, the same as for other providers.
            return parse_generated_answer(message.content)
        except ValueError as exc:
            raise GenerationError(
                f"Local model returned an invalid answer: {exc}"
            ) from exc
