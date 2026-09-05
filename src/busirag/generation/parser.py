import json

from busirag.generation.response import GeneratedAnswer


def parse_generated_answer(
    raw_response: str,
    valid_citation_ids: set[str],
) -> GeneratedAnswer:
    response = raw_response.strip()

    if response.startswith("```json") and response.endswith("```"):
        response = response[len("```json"):-len("```")].strip()

    elif response.startswith("```") and response.endswith("```"):
        response = response[3:-3].strip()

    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")

    answer = data.get("answer")
    citations = data.get("citations")

    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("LLM response must contain a non-empty answer")

    if not isinstance(citations, list):
        raise ValueError("LLM response must contain a citations list")

    if not all(isinstance(citation, str) for citation in citations):
        raise ValueError("All citations must be strings")

    invalid_citations = set(citations) - valid_citation_ids

    if invalid_citations:
        raise ValueError(
            f"LLM returned invalid citations: {sorted(invalid_citations)}"
        )

    return GeneratedAnswer(
        answer=answer,
        citations=citations,
    )