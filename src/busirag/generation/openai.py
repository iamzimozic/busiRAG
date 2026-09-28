import os

from langchain_openai import ChatOpenAI

from busirag.generation.response import GeneratedAnswer


class OpenAIProvider:
    """
    OpenAI chat models with native structured output (JSON schema),
    so answers are returned as GeneratedAnswer like the Gemini provider.
    """

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float | None = 0.0,
    ):
        options = {}

        if temperature is not None:
            options["temperature"] = temperature

        self.llm = ChatOpenAI(
            model=model,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
            **options,
        )

        self.structured_llm = self.llm.with_structured_output(
            GeneratedAnswer
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> GeneratedAnswer:
        return self.structured_llm.invoke(
            [
                ("system", system_prompt),
                ("human", user_prompt),
            ]
        )
