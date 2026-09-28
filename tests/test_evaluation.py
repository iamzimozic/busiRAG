import json
from types import SimpleNamespace

import pytest

from busirag.evaluation import (
    CaseResult,
    EvaluationCase,
    RelevantChunk,
    evaluate_results,
    first_relevant_rank,
    load_cases,
    matches,
    mean_reciprocal_rank,
    percentile,
    recall_at_k,
    render_markdown,
    summarize,
    summarize_by_category,
)


def chunk(chunk_id=1, company="apple", year=2023, text=""):
    return SimpleNamespace(
        chunk_id=chunk_id,
        company=company,
        year=year,
        text=text,
    )


def write_cases(tmp_path, cases):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    return path


def test_load_cases_supports_legacy_chunk_id_format(tmp_path):
    path = write_cases(
        tmp_path,
        [
            {
                "id": "legacy",
                "query": "What was Apple's net income?",
                "relevant_chunks": [
                    {"company": "apple", "year": 2023, "chunk_id": 435}
                ],
                "expected_answer": "$96,995 million",
            }
        ],
    )

    [case] = load_cases(path)

    assert case.category == "uncategorized"
    assert case.relevant_chunks == [
        RelevantChunk(company="apple", year=2023, chunk_id=435)
    ]


def test_load_cases_reads_anchors_groups_and_category(tmp_path):
    path = write_cases(
        tmp_path,
        [
            {
                "id": "comparison",
                "category": "comparison",
                "query": "Compare net income.",
                "relevant_chunks": [
                    {
                        "company": "apple",
                        "year": 2023,
                        "contains": ["net income", "96,995"],
                        "group": "apple",
                    },
                    {
                        "company": "nvidia",
                        "year": 2025,
                        "contains": ["72,880"],
                        "group": "nvidia",
                    },
                ],
                "expected_answer": "...",
            }
        ],
    )

    [case] = load_cases(path)

    assert case.category == "comparison"
    assert case.groups == ["apple", "nvidia"]
    assert case.relevant_chunks[0].contains == ("net income", "96,995")


def test_load_cases_rejects_duplicate_ids(tmp_path):
    raw_case = {
        "id": "dup",
        "query": "q",
        "relevant_chunks": [
            {"company": "apple", "year": 2023, "chunk_id": 1}
        ],
        "expected_answer": "a",
    }

    path = write_cases(tmp_path, [raw_case, raw_case])

    with pytest.raises(ValueError, match="Duplicate"):
        load_cases(path)


def test_load_cases_rejects_spec_without_id_or_anchors(tmp_path):
    path = write_cases(
        tmp_path,
        [
            {
                "id": "empty",
                "query": "q",
                "relevant_chunks": [{"company": "apple", "year": 2023}],
                "expected_answer": "a",
            }
        ],
    )

    with pytest.raises(ValueError, match="neither chunk_id nor contains"):
        load_cases(path)


def test_matches_is_case_and_whitespace_insensitive():
    relevant = RelevantChunk(
        company="Apple",
        year=2023,
        contains=("Net income", "96,995"),
    )

    assert matches(
        chunk(text="NET\xa0INCOME   $  96,995 $ 99,803"),
        relevant,
    )


def test_matches_requires_company_year_and_all_anchors():
    relevant = RelevantChunk(
        company="apple",
        year=2023,
        contains=("net income", "96,995"),
    )

    text = "Net income 96,995"

    assert not matches(chunk(company="nvidia", text=text), relevant)
    assert not matches(chunk(year=2024, text=text), relevant)
    assert not matches(chunk(text="Net income 99,803"), relevant)


def test_matches_checks_chunk_id_when_given():
    relevant = RelevantChunk(company="apple", year=2023, chunk_id=7)

    assert matches(chunk(chunk_id=7), relevant)
    assert not matches(chunk(chunk_id=8), relevant)


def test_first_relevant_rank_accepts_any_alternative():
    case = EvaluationCase(
        id="ni",
        query="q",
        relevant_chunks=[
            RelevantChunk("apple", 2023, contains=("96,995",)),
            RelevantChunk("apple", 2024, contains=("96,995",)),
        ],
        expected_answer="a",
    )

    results = [
        chunk(text="unrelated"),
        chunk(year=2024, text="Net income 93,736 96,995"),
    ]

    assert first_relevant_rank(results, case) == 2


def test_comparison_recall_counts_each_evidence_group():
    case = EvaluationCase(
        id="cmp",
        query="q",
        relevant_chunks=[
            RelevantChunk("apple", 2023, contains=("29,915",), group="a"),
            RelevantChunk("microsoft", 2024, contains=("29,510",), group="m"),
        ],
        expected_answer="a",
        category="comparison",
    )

    results = [chunk(text="R&D 29,915")] + [chunk(text="x")] * 6 + [
        chunk(company="microsoft", year=2024, text="R&D 29,510")
    ]

    result = evaluate_results(results, case)

    assert result.relevant_rank == 1
    assert result.group_ranks == {"a": 1, "m": 8}
    assert recall_at_k([result], 5) == 0.5
    assert recall_at_k([result], 10) == 1.0


def test_recall_and_mrr():
    results = [
        CaseResult("a", "q", relevant_rank=1),
        CaseResult("b", "q", relevant_rank=4),
        CaseResult("c", "q", relevant_rank=None),
        CaseResult("d", "q", relevant_rank=10),
    ]

    assert recall_at_k(results, 5) == 0.5
    assert recall_at_k(results, 10) == 0.75
    assert mean_reciprocal_rank(results) == pytest.approx(
        (1 + 0.25 + 0 + 0.1) / 4
    )
    assert recall_at_k([], 5) == 0.0
    assert mean_reciprocal_rank([]) == 0.0


def test_percentile_interpolates():
    values = [10.0, 20.0, 30.0, 40.0]

    assert percentile(values, 50) == 25.0
    assert percentile(values, 0) == 10.0
    assert percentile(values, 100) == 40.0
    assert percentile([5.0], 95) == 5.0

    with pytest.raises(ValueError):
        percentile([], 50)


def test_summaries_and_markdown():
    results = [
        CaseResult("a", "q", 1, category="narrative", latency_ms=10.0),
        CaseResult("b", "q", None, category="table_numeric", latency_ms=30.0),
    ]

    summary = summarize(results)

    assert summary["cases"] == 2
    assert summary["recall_at_10"] == 0.5
    assert summary["latency_p50_ms"] == 20.0

    by_category = summarize_by_category(results)

    assert by_category["narrative"]["recall_at_10"] == 1.0
    assert by_category["table_numeric"]["recall_at_10"] == 0.0

    report = {
        "config": {
            "cases": 2,
            "documents": 3,
            "top_k": 10,
            "candidate_k": 50,
            "embedding_model": "emb",
            "reranker_model": "rr",
            "device": "cpu",
            "git_commit": "abc123",
        },
        "modes": {
            "dense": {"summary": summary, "by_category": by_category},
        },
    }

    markdown = render_markdown(report)

    assert "| Dense (pgvector) | 0.500 | 0.500 | 0.500 | 20 ms |" in markdown
    assert "narrative (n=1)" in markdown
    assert "commit `abc123`" in markdown
