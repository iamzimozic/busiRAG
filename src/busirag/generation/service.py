from busirag.generation.base import LLMProvider
from busirag.generation.context import build_context
from busirag.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from busirag.generation.response import RAGResponse


class GenerationService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def generate(self, query, retrieval_results) -> RAGResponse:
        context_items = build_context(retrieval_results)

        context = "\n\n".join(
            f"[{item.citation_id}] "
            f"Company: {item.company} | "
            f"Year: {item.year} | "
            f"Page: {item.page_number}\n"
            f"{item.text}"
            for item in context_items
        )

        user_prompt = build_user_prompt(
            query=query,
            context=context,
        )

        generated_answer = self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        valid_citation_ids = {
            item.citation_id for item in context_items
        }

        invalid_citations = (
            set(generated_answer.citations) - valid_citation_ids
        )

        if invalid_citations:
            raise ValueError(
                f"LLM returned invalid citations: {sorted(invalid_citations)}"
            )

        sources = [
            item
            for item in context_items
            if item.citation_id in generated_answer.citations
        ]

        return RAGResponse(
            answer=generated_answer.answer,
            sources=sources,
        )