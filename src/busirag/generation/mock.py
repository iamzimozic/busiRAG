from busirag.generation.response import GeneratedAnswer


class MockLLMProvider:
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> GeneratedAnswer:
        return GeneratedAnswer(
            answer="MOCK ANSWER",
            citations=[],
        )

class ScriptedLLMProvider:
    """
    Deterministic provider for tests: returns the scripted answer
    for the first key that appears in the user prompt.
    """

    def __init__(
        self,
        responses: dict[str, GeneratedAnswer],
        default: GeneratedAnswer | None = None,
    ):
        self.responses = responses
        self.default = default or GeneratedAnswer(
            answer="The available sources are insufficient.",
            citations=[],
        )
        self.calls: list[tuple[str, str]] = []

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> GeneratedAnswer:
        self.calls.append((system_prompt, user_prompt))

        for key, response in self.responses.items():
            if key in user_prompt:
                return response

        return self.default
