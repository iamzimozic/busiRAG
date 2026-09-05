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