import json
from pathlib import Path

import pytest

from busirag.answer_evaluation import (
    AnswerCase,
    AnswerCheck,
    ExpectedAnswer,
    ExpectedFigure,
    check_citations,
    check_figure,
    evaluate_answer,
    extract_numbers,
    is_refusal,
    load_answer_cases,
    render_answer_markdown,
    summarize_answers,
)
from busirag.evaluation import RelevantChunk
from busirag.generation.context import build_context
from busirag.generation.mock import ScriptedLLMProvider
from busirag.generation.response import GeneratedAnswer
from busirag.generation.service import GenerationService
from busirag.retrieval.vector import RetrievalResult

MILLION = ExpectedFigure(value=96995, unit="million")


def retrieval_result(chunk_id, company, year, text):
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=chunk_id,
        text=text,
        company=company,
        filename=f"{company}-{year}.pdf",
        year=year,
        page_number=1,
        section=None,
        element_type="table",
        similarity=0.9,
    )


APPLE_INCOME = retrieval_result(
    1, "apple", 2023, "Net income $ 96,995 $ 99,803 $ 94,680"
)
APPLE_RISK = retrieval_result(
    2, "apple", 2023, "Restrictions on international trade, such as tariffs"
)
NVIDIA_INCOME = retrieval_result(
    3, "nvidia", 2025, "Net income $ 72,880 $ 29,760"
)

NET_INCOME_CASE = AnswerCase(
    id="apple_ni",
    query="What was Apple's net income in 2023?",
    answerable=True,
    expected=ExpectedAnswer(figures=(MILLION,), period="2023"),
    evidence=(
        RelevantChunk("apple", 2023, contains=("net income", "96,995")),
    ),
)

UNANSWERABLE_CASE = AnswerCase(
    id="tesla",
    query="What was Tesla's revenue in 2024?",
    answerable=False,
)


@pytest.mark.parametrize(
    "answer",
    [
        "Apple's net income in 2023 was $96,995 million.",
        "Net income was $97.0 billion for fiscal 2023.",
        "It reported 96,995 million dollars.",
        "Net income: $96.995B",
        "$96,995,000,000",
    ],
)
def test_numeric_check_accepts_equivalent_units(answer):
    assert check_figure(answer, MILLION) == "correct"


@pytest.mark.parametrize(
    ("answer", "result"),
    [
        ("Net income was $96,995.", "wrong_unit"),
        ("Net income was $96,995 billion.", "wrong_unit"),
        ("Net income was $99,803 million.", "wrong_value"),
        ("Net income was $95 billion.", "wrong_value"),
        ("Apple reported strong net income.", "no_number"),
    ],
)
def test_numeric_check_flags_errors(answer, result):
    assert check_figure(answer, MILLION) == result


def test_percent_figures_only_match_percentages():
    figure = ExpectedFigure(value=15.7, unit="percent")

    assert check_figure("The CET1 ratio was 15.7%.", figure) == "correct"
    assert check_figure("CET1 was 15.7 percent", figure) == "correct"
    assert check_figure("CET1 was $15.7 billion", figure) == "no_number"


def test_extract_numbers_reads_scale_words():
    numbers = extract_numbers("Revenue of $168.9 billion, up 23%.")

    assert [n.value for n in numbers] == [168.9e9, 23]
    assert [n.is_percent for n in numbers] == [False, True]


@pytest.mark.parametrize(
    "answer",
    [
        "The available sources are insufficient to answer this question.",
        "The provided sources do not contain information about Tesla.",
        "I cannot determine Tesla's revenue from these documents.",
        "There is no information about Amazon in the sources.",
    ],
)
def test_refusals_are_detected(answer):
    assert is_refusal(answer)


def test_normal_answers_are_not_refusals():
    assert not is_refusal("Apple's net income in 2023 was $96,995 million.")


def test_citations_must_point_to_evidence():
    supporting, unrelated = build_context([APPLE_INCOME, APPLE_RISK])

    assert check_citations([supporting], NET_INCOME_CASE) == (True, 1.0)
    assert check_citations([unrelated], NET_INCOME_CASE) == (False, 0.0)
    assert check_citations(
        [supporting, unrelated],
        NET_INCOME_CASE,
    ) == (True, 0.5)
    assert check_citations([], NET_INCOME_CASE) == (False, None)


def test_citations_fall_back_to_expected_figure_without_evidence():
    case = AnswerCase(
        id="no_evidence",
        query="q",
        answerable=True,
        expected=ExpectedAnswer(figures=(MILLION,)),
    )

    [source] = build_context([APPLE_INCOME])

    assert check_citations([source], case) == (True, 1.0)


def test_comparison_citations_need_every_group():
    case = AnswerCase(
        id="cmp",
        query="q",
        answerable=True,
        expected=ExpectedAnswer(
            figures=(
                MILLION,
                ExpectedFigure(value=72880, unit="million"),
            )
        ),
        evidence=(
            RelevantChunk("apple", 2023, contains=("96,995",), group="a"),
            RelevantChunk("nvidia", 2025, contains=("72,880",), group="n"),
        ),
    )

    apple, nvidia = build_context([APPLE_INCOME, NVIDIA_INCOME])

    assert check_citations([apple], case)[0] is False
    assert check_citations([apple, nvidia], case)[0] is True

    check = evaluate_answer(
        case,
        "Apple earned $96,995 million versus NVIDIA's $72,880 million.",
        [apple, nvidia],
    )

    assert check.passed
    assert check.numeric_result == "correct"


def test_answer_with_wrong_unit_and_unsupported_citation_fails():
    [unrelated] = build_context([APPLE_RISK])

    check = evaluate_answer(
        NET_INCOME_CASE,
        "Net income was $96,995.",
        [unrelated],
    )

    assert not check.passed
    assert check.failures == [
        "numeric_wrong_unit",
        "citations_do_not_support_answer",
    ]
    assert check.period_stated is False


def test_unanswerable_case_passes_only_on_refusal():
    refused = evaluate_answer(
        UNANSWERABLE_CASE,
        "The available sources are insufficient.",
        [],
    )
    answered = evaluate_answer(
        UNANSWERABLE_CASE,
        "Tesla's revenue was $97,690 million.",
        [],
    )

    assert refused.passed
    assert not answered.passed
    assert answered.failures == ["answered_unanswerable_question"]


def test_false_refusal_fails_answerable_case():
    [source] = build_context([APPLE_INCOME])

    check = evaluate_answer(
        NET_INCOME_CASE,
        "The sources do not contain Apple's 2023 net income.",
        [source],
    )

    assert not check.passed
    assert "false_refusal" in check.failures


def test_end_to_end_with_scripted_provider():
    """
    Run cases through the real GenerationService (prompt building,
    citation validation, source selection) with a scripted LLM.
    """

    llm = ScriptedLLMProvider(
        {
            "Apple's net income": GeneratedAnswer(
                answer="Apple's net income in 2023 was $96,995 million.",
                citations=["S1"],
            ),
        }
    )

    service = GenerationService(llm)

    checks = []

    for case, retrieved in [
        (NET_INCOME_CASE, [APPLE_INCOME, APPLE_RISK]),
        (UNANSWERABLE_CASE, [APPLE_RISK]),
    ]:
        response = service.generate(case.query, retrieved)
        checks.append(
            evaluate_answer(
                case,
                response.answer,
                response.sources,
                latency_ms=10.0,
            )
        )

    assert [check.passed for check in checks] == [True, True]
    assert checks[0].citations == ["S1"]
    assert checks[0].citation_precision == 1.0
    assert "[S1]" in llm.calls[0][1]

    summary = summarize_answers(checks)

    assert summary["pass_rate"] == 1.0
    assert summary["numeric_accuracy"] == 1.0
    assert summary["citation_support_rate"] == 1.0
    assert summary["refusal_accuracy"] == 1.0
    assert summary["false_refusal_rate"] == 0.0

    report = {
        "config": {
            "provider": "scripted",
            "model": "none",
            "retrieval_mode": "hybrid_rerank",
            "git_commit": "abc123",
        },
        "summary": summary,
        "cases": [check.__dict__ for check in checks],
    }

    markdown = render_answer_markdown(report)

    assert "| Overall pass rate | 100% (2 questions) |" in markdown
    assert "Failures:" not in markdown


def test_load_answer_cases_validates(tmp_path):
    path = tmp_path / "answers.json"

    path.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "query": "q",
                    "expected": {"value": 1, "unit": "gazillion"},
                }
            ]
        )
    )

    with pytest.raises(ValueError, match="unknown unit"):
        load_answer_cases(path)

    path.write_text(json.dumps([{"id": "a", "query": "q"}]))

    with pytest.raises(ValueError, match="needs expected"):
        load_answer_cases(path)


@pytest.mark.parametrize(
    "filename",
    ["answers.json", "answers.template.json"],
)
def test_shipped_answer_files_load(filename):
    cases = load_answer_cases(
        Path("data/evaluation") / filename
    )

    assert cases
    assert any(not case.answerable for case in cases)


def test_same_company_chunk_stating_rounded_figure_supports_answer():
    case = AnswerCase(
        id="dc",
        query="What was NVIDIA's Data Center revenue in fiscal 2025?",
        answerable=True,
        expected=ExpectedAnswer(
            figures=(ExpectedFigure(value=115186, unit="million"),)
        ),
        evidence=(
            RelevantChunk(
                "nvidia",
                2025,
                contains=("data center", "115,186"),
            ),
        ),
    )

    summary, other_company, unrelated = build_context(
        [
            retrieval_result(
                10, "nvidia", 2025, "Data Center $115.2 billion revenue"
            ),
            retrieval_result(11, "apple", 2025, "Revenue $115.2 billion"),
            retrieval_result(12, "nvidia", 2025, "Gaming $11.4 billion"),
        ]
    )

    assert check_citations([summary], case) == (True, 1.0)
    assert check_citations([other_company], case) == (False, 0.0)
    assert check_citations([unrelated], case) == (False, 0.0)


def test_errors_are_excluded_from_rates_and_reported():
    [source] = build_context([APPLE_INCOME])

    passed = evaluate_answer(
        NET_INCOME_CASE,
        "Net income was $96,995 million in 2023.",
        [source],
    )

    errored = AnswerCheck(
        case_id="tesla",
        query=UNANSWERABLE_CASE.query,
        answerable=False,
        answer="",
        citations=[],
        refused=False,
        error="GoogleRateLimitError: 429 RESOURCE_EXHAUSTED",
    )

    summary = summarize_answers([passed, errored])

    assert summary["completed"] == 1
    assert summary["errors"] == 1
    assert summary["pass_rate"] == 1.0
    assert summary["unanswerable_cases"] == 0

    markdown = render_answer_markdown(
        {
            "config": {
                "provider": "gemini",
                "model": "m",
                "retrieval_mode": "hybrid_rerank",
                "git_commit": "abc",
            },
            "summary": summary,
            "cases": [passed.__dict__, errored.__dict__],
        }
    )

    assert "1 of 2 questions errored" in markdown
    assert "`tesla`: error: GoogleRateLimitError" in markdown
    assert passed.cited_sources == [
        {
            "citation_id": "S1",
            "chunk_id": 1,
            "company": "apple",
            "year": 2023,
            "page_number": 1,
        }
    ]
