from typing import Protocol

from busirag.generation.response import GeneratedAnswer


class LLMProvider(Protocol):
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> GeneratedAnswer: ...