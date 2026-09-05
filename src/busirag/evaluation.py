import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RelevantChunk:
    company: str
    year: int
    chunk_id: int


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    query: str
    relevant_chunks: list[RelevantChunk]
    expected_answer: str


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    query: str
    relevant_rank: int | None


def load_cases(path: Path) -> list[EvaluationCase]:
    with path.open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)

    cases = []

    for raw_case in raw_cases:
        relevant_chunks = [
            RelevantChunk(
                company=chunk["company"],
                year=chunk["year"],
                chunk_id=chunk["chunk_id"],
            )
            for chunk in raw_case["relevant_chunks"]
        ]

        cases.append(
            EvaluationCase(
                id=raw_case["id"],
                query=raw_case["query"],
                relevant_chunks=relevant_chunks,
                expected_answer=raw_case["expected_answer"],
            )
        )

    return cases


def is_relevant(
    chunk_id: int,
    company: str,
    year: int,
    case: EvaluationCase,
) -> bool:
    return any(
        relevant.chunk_id == chunk_id
        and relevant.company == company
        and relevant.year == year
        for relevant in case.relevant_chunks
    )


def first_relevant_rank(
    results,
    case: EvaluationCase,
) -> int | None:
    for rank, result in enumerate(results, start=1):
        if is_relevant(
            result.chunk_id,
            result.company,
            result.year,
            case,
        ):
            return rank

    return None