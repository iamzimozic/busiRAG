import json
import math
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GROUP = "default"


@dataclass(frozen=True)
class RelevantChunk:
    """
    A description of a chunk that answers (part of) a case.

    A retrieved chunk matches when company and year are equal and,
    if given, its id equals chunk_id and its text contains every
    string in `contains` (case- and whitespace-insensitive).

    Text anchors survive re-ingestion; chunk ids do not.

    Specs sharing a `group` are alternatives for the same piece of
    evidence (e.g. net income in the income statement or in the cash
    flow statement). Cases that need several pieces of evidence, such
    as comparisons, use one group per piece.
    """

    company: str
    year: int
    chunk_id: int | None = None
    contains: tuple[str, ...] = ()
    group: str = DEFAULT_GROUP


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    query: str
    relevant_chunks: list[RelevantChunk]
    expected_answer: str
    category: str = "uncategorized"

    @property
    def groups(self) -> list[str]:
        return sorted(
            {chunk.group for chunk in self.relevant_chunks}
        )


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    query: str
    relevant_rank: int | None
    group_ranks: dict[str, int | None] = field(default_factory=dict)
    category: str = "uncategorized"
    latency_ms: float | None = None


def load_cases(path: Path) -> list[EvaluationCase]:
    with path.open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)

    cases = []
    seen_ids = set()

    for raw_case in raw_cases:
        if raw_case["id"] in seen_ids:
            raise ValueError(
                f"Duplicate evaluation case id: {raw_case['id']!r}"
            )

        seen_ids.add(raw_case["id"])

        relevant_chunks = [
            RelevantChunk(
                company=chunk["company"],
                year=chunk["year"],
                chunk_id=chunk.get("chunk_id"),
                contains=tuple(chunk.get("contains", ())),
                group=chunk.get("group", DEFAULT_GROUP),
            )
            for chunk in raw_case["relevant_chunks"]
        ]

        for chunk in relevant_chunks:
            if chunk.chunk_id is None and not chunk.contains:
                raise ValueError(
                    f"Case {raw_case['id']!r} has a relevant chunk "
                    "with neither chunk_id nor contains."
                )

        cases.append(
            EvaluationCase(
                id=raw_case["id"],
                query=raw_case["query"],
                relevant_chunks=relevant_chunks,
                expected_answer=raw_case["expected_answer"],
                category=raw_case.get("category", "uncategorized"),
            )
        )

    return cases


def normalize_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").lower().split())


def matches(result, relevant: RelevantChunk) -> bool:
    if result.company.lower() != relevant.company.lower():
        return False

    if result.year != relevant.year:
        return False

    if (
        relevant.chunk_id is not None
        and result.chunk_id != relevant.chunk_id
    ):
        return False

    text = normalize_text(result.text)

    return all(
        normalize_text(anchor) in text
        for anchor in relevant.contains
    )


def is_relevant(result, case: EvaluationCase) -> bool:
    return any(
        matches(result, relevant)
        for relevant in case.relevant_chunks
    )


def first_relevant_rank(
    results,
    case: EvaluationCase,
) -> int | None:
    for rank, result in enumerate(results, start=1):
        if is_relevant(result, case):
            return rank

    return None


def group_ranks(
    results,
    case: EvaluationCase,
) -> dict[str, int | None]:
    """First rank at which each evidence group is satisfied."""

    ranks: dict[str, int | None] = {
        group: None for group in case.groups
    }

    for rank, result in enumerate(results, start=1):
        for relevant in case.relevant_chunks:
            if ranks[relevant.group] is None and matches(
                result, relevant
            ):
                ranks[relevant.group] = rank

    return ranks


def evaluate_results(
    results,
    case: EvaluationCase,
    latency_ms: float | None = None,
) -> CaseResult:
    return CaseResult(
        case_id=case.id,
        query=case.query,
        relevant_rank=first_relevant_rank(results, case),
        group_ranks=group_ranks(results, case),
        category=case.category,
        latency_ms=latency_ms,
    )


def case_recall_at_k(result: CaseResult, k: int) -> float:
    """
    Fraction of a case's evidence groups found in the top k.

    For single-group cases this is 1.0 on a hit and 0.0 on a miss.
    """

    ranks = result.group_ranks or {
        DEFAULT_GROUP: result.relevant_rank
    }

    found = sum(
        rank is not None and rank <= k
        for rank in ranks.values()
    )

    return found / len(ranks)


def recall_at_k(results: list[CaseResult], k: int) -> float:
    if not results:
        return 0.0

    return sum(
        case_recall_at_k(result, k) for result in results
    ) / len(results)


def mean_reciprocal_rank(results: list[CaseResult]) -> float:
    if not results:
        return 0.0

    return sum(
        1.0 / result.relevant_rank
        if result.relevant_rank is not None
        else 0.0
        for result in results
    ) / len(results)


def percentile(values: list[float], pct: float) -> float:
    """Percentile with linear interpolation between closest ranks."""

    if not values:
        raise ValueError("values must not be empty")

    if not 0 <= pct <= 100:
        raise ValueError("pct must be between 0 and 100")

    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    weight = position - lower

    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize(results: list[CaseResult]) -> dict[str, float | int]:
    summary: dict[str, float | int] = {
        "cases": len(results),
        "recall_at_5": recall_at_k(results, 5),
        "recall_at_10": recall_at_k(results, 10),
        "mrr": mean_reciprocal_rank(results),
    }

    latencies = [
        result.latency_ms
        for result in results
        if result.latency_ms is not None
    ]

    if latencies:
        summary["latency_p50_ms"] = percentile(latencies, 50)
        summary["latency_p95_ms"] = percentile(latencies, 95)

    return summary


def summarize_by_category(
    results: list[CaseResult],
) -> dict[str, dict[str, float | int]]:
    categories = sorted({result.category for result in results})

    return {
        category: summarize(
            [
                result
                for result in results
                if result.category == category
            ]
        )
        for category in categories
    }


MODE_LABELS = {
    "dense": "Dense (pgvector)",
    "sparse": "Sparse (Postgres FTS)",
    "hybrid": "Hybrid (RRF)",
    "hybrid_rerank": "Hybrid + reranker",
}


def render_markdown(report: dict) -> str:
    """Render an ablation report produced by scripts/evaluate_ablation.py."""

    config = report["config"]
    modes = report["modes"]

    lines = [
        "| Retrieval | Recall@5 | Recall@10 | MRR | p50 latency | p95 latency |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for mode, data in modes.items():
        summary = data["summary"]

        lines.append(
            f"| {MODE_LABELS.get(mode, mode)} "
            f"| {summary['recall_at_5']:.3f} "
            f"| {summary['recall_at_10']:.3f} "
            f"| {summary['mrr']:.3f} "
            f"| {summary['latency_p50_ms']:.0f} ms "
            f"| {summary['latency_p95_ms']:.0f} ms |"
        )

    categories = sorted(
        {
            category
            for data in modes.values()
            for category in data["by_category"]
        }
    )

    first_mode = next(iter(modes.values()))

    lines += [
        "",
        "Recall@10 by question type:",
        "",
        "| Retrieval | "
        + " | ".join(
            f"{category} (n={first_mode['by_category'][category]['cases']})"
            for category in categories
        )
        + " |",
        "|---|" + "---:|" * len(categories),
    ]

    for mode, data in modes.items():
        lines.append(
            f"| {MODE_LABELS.get(mode, mode)} | "
            + " | ".join(
                f"{data['by_category'][category]['recall_at_10']:.3f}"
                for category in categories
            )
            + " |"
        )

    lines += [
        "",
        f"{config['cases']} questions over {config['documents']} "
        f"filings; top_k={config['top_k']}, "
        f"candidate_k={config['candidate_k']}; "
        f"embeddings `{config['embedding_model']}`, "
        f"reranker `{config['reranker_model']}`; "
        f"latency measured on {config['device']} "
        f"(commit `{config['git_commit']}`).",
    ]

    return "\n".join(lines) + "\n"
