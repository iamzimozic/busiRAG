import os

from langchain_google_genai import ChatGoogleGenerativeAI

from busirag.generation.response import GeneratedAnswer


class GeminiProvider:
    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
    ):
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key or os.getenv("GEMINI_API_KEY"),
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