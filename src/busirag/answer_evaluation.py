"""
End-to-end answer evaluation.

Checks a generated answer (answer text + cited sources) against an
expected answer:

- numeric:  the answer states the expected figure in the right units
            (e.g. "$96,995 million" == "$97.0 billion" within tolerance,
            but "$96,995" alone is a unit error)
- content:  free-text answers mention every required phrase
- citations: at least one cited source is a chunk that actually
            contains the supporting evidence
- refusal:  questions the documents cannot answer are declined, and
            answerable questions are not

Case file format (see data/evaluation/answers.template.json):

{
  "id": "apple_net_income_2023",
  "query": "What was Apple's net income in 2023?",
  "answerable": true,
  "expected": {
    "value": 96995, "unit": "million", "currency": "USD",
    "tolerance": 0.005, "period": "2023",
    "must_include": ["..."]
  },
  "evidence": [
    {"company": "apple", "year": 2023, "contains": ["net income", "96,995"]}
  ]
}

Comparison questions list several figures instead of one value:

  "expected": {"figures": [{"value": 101832, "unit": "million"},
                           {"value": 72880, "unit": "million"}]}
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from busirag.evaluation import RelevantChunk, matches

SCALES = {
    "trillion": 1e12,
    "tn": 1e12,
    "t": 1e12,
    "billion": 1e9,
    "bn": 1e9,
    "b": 1e9,
    "million": 1e6,
    "mn": 1e6,
    "m": 1e6,
    "thousand": 1e3,
    "k": 1e3,
}

UNITS = {
    "trillion": 1e12,
    "billion": 1e9,
    "million": 1e6,
    "thousand": 1e3,
    "count": 1.0,
    "units": 1.0,
    "percent": 1.0,
}

NUMBER_PATTERN = re.compile(
    r"(?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s*(?P<unit>%|percent\b|trillion\b|billion\b|million\b"
    r"|thousand\b|tn\b|bn\b|mn\b|[TBMK]\b))?",
    re.IGNORECASE,
)

REFUSAL_PATTERNS = [
    r"\binsufficient\b",
    r"\bnot (?:enough|sufficient) (?:information|data|context)\b",
    r"\b(?:do|does) not (?:contain|include|provide|mention|specify)\b",
    r"\bnot (?:contained|included|provided|mentioned|specified|available)\b",
    r"\b(?:cannot|can't|unable to) (?:be )?(?:answer|determine|find|provide)",
    r"\bno (?:information|data|mention)\b",
]

DEFAULT_TOLERANCE = 0.005


@dataclass(frozen=True)
class ExtractedNumber:
    text: str
    value: float
    is_percent: bool


@dataclass(frozen=True)
class ExpectedFigure:
    value: float
    unit: str = "units"
    tolerance: float = DEFAULT_TOLERANCE

    @property
    def is_percent(self) -> bool:
        return self.unit == "percent"

    @property
    def base_value(self) -> float:
        return self.value * UNITS[self.unit]


@dataclass(frozen=True)
class ExpectedAnswer:
    figures: tuple[ExpectedFigure, ...] = ()
    currency: str | None = None
    period: str | None = None
    must_include: tuple[str, ...] = ()

    @property
    def is_numeric(self) -> bool:
        return bool(self.figures)


@dataclass(frozen=True)
class AnswerCase:
    id: str
    query: str
    answerable: bool
    expected: ExpectedAnswer = field(default_factory=ExpectedAnswer)
    evidence: tuple[RelevantChunk, ...] = ()
    category: str = "uncategorized"


@dataclass
class AnswerCheck:
    case_id: str
    query: str
    answerable: bool
    answer: str
    citations: list[str]
    refused: bool
    cited_sources: list[dict] = field(default_factory=list)
    numeric_result: str | None = None
    period_stated: bool | None = None
    content_match: bool | None = None
    citation_supported: bool | None = None
    citation_precision: float | None = None
    passed: bool = False
    failures: list[str] = field(default_factory=list)
    latency_ms: float | None = None
    error: str | None = None


def load_answer_cases(path: Path) -> list[AnswerCase]:
    with path.open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)

    cases = []
    seen_ids = set()

    for raw_case in raw_cases:
        case_id = raw_case["id"]

        if case_id in seen_ids:
            raise ValueError(f"Duplicate answer case id: {case_id!r}")

        seen_ids.add(case_id)

        raw_expected = raw_case.get("expected", {})

        raw_figures = raw_expected.get("figures", [])

        if "value" in raw_expected:
            raw_figures = [raw_expected, *raw_figures]

        figures = []

        for raw_figure in raw_figures:
            unit = raw_figure.get("unit", "units")

            if unit not in UNITS:
                raise ValueError(
                    f"Case {case_id!r} has unknown unit {unit!r}. "
                    f"Expected one of: {', '.join(UNITS)}"
                )

            figures.append(
                ExpectedFigure(
                    value=raw_figure["value"],
                    unit=unit,
                    tolerance=raw_figure.get(
                        "tolerance",
                        raw_expected.get("tolerance", DEFAULT_TOLERANCE),
                    ),
                )
            )

        expected = ExpectedAnswer(
            figures=tuple(figures),
            currency=raw_expected.get("currency"),
            period=raw_expected.get("period"),
            must_include=tuple(raw_expected.get("must_include", ())),
        )

        answerable = raw_case.get("answerable", True)

        if (
            answerable
            and not expected.is_numeric
            and not expected.must_include
        ):
            raise ValueError(
                f"Answerable case {case_id!r} needs expected.value, "
                "expected.figures or expected.must_include."
            )

        evidence = tuple(
            RelevantChunk(
                company=item["company"],
                year=item["year"],
                chunk_id=item.get("chunk_id"),
                contains=tuple(item.get("contains", ())),
                group=item.get("group", "default"),
            )
            for item in raw_case.get("evidence", ())
        )

        cases.append(
            AnswerCase(
                id=case_id,
                query=raw_case["query"],
                answerable=answerable,
                expected=expected,
                evidence=evidence,
                category=raw_case.get("category", "uncategorized"),
            )
        )

    return cases


def extract_numbers(text: str) -> list[ExtractedNumber]:
    numbers = []

    for match in NUMBER_PATTERN.finditer(text):
        raw_number = match.group("number")
        unit = (match.group("unit") or "").lower()

        value = float(raw_number.replace(",", ""))
        is_percent = unit in {"%", "percent"}

        if not is_percent and unit:
            value *= SCALES[unit]

        numbers.append(
            ExtractedNumber(
                text=match.group(0).strip(),
                value=value,
                is_percent=is_percent,
            )
        )

    return numbers


def _close(actual: float, expected: float, tolerance: float) -> bool:
    if expected == 0:
        return actual == 0

    return abs(actual - expected) / abs(expected) <= tolerance


def check_figure(answer: str, figure: ExpectedFigure) -> str:
    """
    Return "correct", "wrong_unit", "wrong_value" or "no_number".

    wrong_unit means the right digits at the wrong scale, e.g. the
    answer says "$96,995" or "$96,995 billion" for $96,995 million.
    """

    numbers = [
        number
        for number in extract_numbers(answer)
        if number.is_percent == figure.is_percent
    ]

    if not numbers:
        return "no_number"

    target = figure.base_value

    if any(
        _close(number.value, target, figure.tolerance)
        for number in numbers
    ):
        return "correct"

    for number in numbers:
        for scale in (1e-12, 1e-9, 1e-6, 1e-3, 1e3, 1e6, 1e9, 1e12):
            if _close(number.value * scale, target, figure.tolerance):
                return "wrong_unit"

    return "wrong_value"


def check_numeric(answer: str, expected: ExpectedAnswer) -> str:
    """Every expected figure must be stated; report the first problem."""

    for figure in expected.figures:
        result = check_figure(answer, figure)

        if result != "correct":
            return result

    return "correct"


def is_refusal(answer: str) -> bool:
    text = answer.lower()

    return any(
        re.search(pattern, text) for pattern in REFUSAL_PATTERNS
    )


def states_figure(text: str, figure: ExpectedFigure) -> bool:
    """
    Whether source text states a figure, in any common rendering.

    Financial tables print values without a scale word ("96,995" in a
    table "in millions"), so digits that match at another scale count
    too, as do rounded forms such as "$97.0 billion".
    """

    return check_figure(text, figure) in {"correct", "wrong_unit"}


def _supports(source, relevant: RelevantChunk, case: AnswerCase) -> bool:
    if matches(source, relevant):
        return True

    return (
        case.expected.is_numeric
        and source.company.lower() == relevant.company.lower()
        and any(
            states_figure(source.text, figure)
            for figure in case.expected.figures
        )
    )


def check_citations(
    sources,
    case: AnswerCase,
) -> tuple[bool, float | None]:
    """
    Return (supported, precision) for the cited sources.

    A cited source supports an evidence spec when it matches the spec
    (company, year, anchors) or, for numeric answers, when it is from
    the same company and states an expected figure.

    supported: every evidence group is covered by a cited source.
    precision: share of cited sources that support the answer.
    """

    if not sources:
        return False, None

    if case.evidence:
        groups = {relevant.group for relevant in case.evidence}

        covered = {
            relevant.group
            for relevant in case.evidence
            if any(
                _supports(source, relevant, case)
                for source in sources
            )
        }

        relevant_sources = [
            source
            for source in sources
            if any(
                _supports(source, relevant, case)
                for relevant in case.evidence
            )
        ]

        return (
            covered == groups,
            len(relevant_sources) / len(sources),
        )

    if case.expected.is_numeric:
        relevant_sources = [
            source
            for source in sources
            if any(
                states_figure(source.text, figure)
                for figure in case.expected.figures
            )
        ]

        return (
            bool(relevant_sources),
            len(relevant_sources) / len(sources),
        )

    return False, None


def evaluate_answer(
    case: AnswerCase,
    answer: str,
    sources,
    latency_ms: float | None = None,
) -> AnswerCheck:
    refused = is_refusal(answer)

    check = AnswerCheck(
        case_id=case.id,
        query=case.query,
        answerable=case.answerable,
        answer=answer,
        citations=[source.citation_id for source in sources],
        refused=refused,
        cited_sources=[
            {
                "citation_id": source.citation_id,
                "chunk_id": source.chunk_id,
                "company": source.company,
                "year": source.year,
                "page_number": source.page_number,
            }
            for source in sources
        ],
        latency_ms=latency_ms,
    )

    if not case.answerable:
        if not refused:
            check.failures.append("answered_unanswerable_question")

        if sources:
            check.failures.append("cited_sources_for_refusal")

        check.passed = refused

        return check

    if refused:
        check.failures.append("false_refusal")

    expected = case.expected

    if expected.is_numeric:
        check.numeric_result = check_numeric(answer, expected)

        if check.numeric_result != "correct":
            check.failures.append(f"numeric_{check.numeric_result}")

    if expected.period is not None:
        check.period_stated = expected.period.lower() in answer.lower()

    if expected.must_include:
        text = answer.lower()
        check.content_match = all(
            phrase.lower() in text for phrase in expected.must_include
        )

        if not check.content_match:
            check.failures.append("missing_required_content")

    supported, precision = check_citations(sources, case)
    check.citation_supported = supported
    check.citation_precision = precision

    if not supported:
        check.failures.append("citations_do_not_support_answer")

    check.passed = not check.failures

    return check


def _rate(values: list[bool]) -> float | None:
    if not values:
        return None

    return sum(values) / len(values)


def summarize_answers(checks: list[AnswerCheck]) -> dict:
    answerable = [
        check for check in checks
        if check.answerable and check.error is None
    ]
    unanswerable = [
        check for check in checks
        if not check.answerable and check.error is None
    ]
    numeric = [
        check for check in answerable
        if check.numeric_result is not None
    ]
    precisions = [
        check.citation_precision
        for check in answerable
        if check.citation_precision is not None
    ]
    latencies = [
        check.latency_ms
        for check in checks
        if check.latency_ms is not None
    ]

    completed = [check for check in checks if check.error is None]

    return {
        "cases": len(checks),
        "completed": len(completed),
        "errors": len(checks) - len(completed),
        "pass_rate": _rate([check.passed for check in completed]),
        "numeric_cases": len(numeric),
        "numeric_accuracy": _rate(
            [check.numeric_result == "correct" for check in numeric]
        ),
        "numeric_unit_errors": sum(
            check.numeric_result == "wrong_unit" for check in numeric
        ),
        "period_stated_rate": _rate(
            [
                check.period_stated
                for check in answerable
                if check.period_stated is not None
            ]
        ),
        "citation_support_rate": _rate(
            [bool(check.citation_supported) for check in answerable]
        ),
        "citation_precision": (
            sum(precisions) / len(precisions) if precisions else None
        ),
        "unanswerable_cases": len(unanswerable),
        "refusal_accuracy": _rate(
            [check.refused for check in unanswerable]
        ),
        "false_refusal_rate": _rate(
            [check.refused for check in answerable]
        ),
        "mean_latency_ms": (
            sum(latencies) / len(latencies) if latencies else None
        ),
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def render_answer_markdown(report: dict) -> str:
    summary = report["summary"]
    config = report["config"]

    lines = [
        "| Metric | Result |",
        "|---|---:|",
        f"| Overall pass rate | {_pct(summary['pass_rate'])} "
        f"({summary['completed']} questions) |",
        f"| Numeric answers correct (value + unit) | "
        f"{_pct(summary['numeric_accuracy'])} "
        f"(n={summary['numeric_cases']}) |",
        f"| Citations support the answer | "
        f"{_pct(summary['citation_support_rate'])} |",
        f"| Citation precision | "
        f"{_pct(summary['citation_precision'])} |",
        f"| Correct refusals on unanswerable questions | "
        f"{_pct(summary['refusal_accuracy'])} "
        f"(n={summary['unanswerable_cases']}) |",
        f"| False refusals on answerable questions | "
        f"{_pct(summary['false_refusal_rate'])} |",
        "",
        f"Provider `{config['provider']}` / model `{config['model']}`, "
        f"retrieval `{config['retrieval_mode']}` "
        f"(commit `{config['git_commit']}`).",
    ]

    if summary["errors"]:
        lines += [
            "",
            f"**{summary['errors']} of {summary['cases']} questions "
            "errored (e.g. provider rate limits) and are excluded "
            "from the results above.**",
        ]

    failures = [
        check for check in report["cases"]
        if not check["passed"]
    ]

    if failures:
        lines += ["", "Failures:", ""]

        for check in failures:
            reasons = (
                f"error: {check['error'][:120]}"
                if check["error"]
                else ", ".join(check["failures"])
            )
            lines.append(f"- `{check['case_id']}`: {reasons}")

    return "\n".join(lines) + "\n"
