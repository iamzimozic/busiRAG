# Demo questions

Questions for the public demo, built on the 10-K / annual-report corpus in `data/raw/` (Apple 2022–2025, Microsoft 2023–2025, NVIDIA 2024–2026, JPMorgan Chase 2024–2025).

Every expected answer below was checked against the ingested chunk text. The **Hybrid** and **+ Reranker** columns give the rank of the first supporting chunk in the retrieval benchmark (`data/evaluation/results/retrieval_ablation.json`; lower is better, top 10 is passed to the LLM). Answer generation was not re-verified for every question — run a question once before showing it live.

## Tables and exact figures

| # | Question | Expected answer | Hybrid | + Reranker |
|---|---|---|---:|---:|
| 1 | What was Apple's net income in 2023? | $96,995 million | 1 | 1 |
| 2 | What was Apple's net income in 2022? | $99,803 million | 2 | 1 |
| 3 | How much long-lived assets did Apple have in China in 2023? | $5,778 million | 2 | 1 |
| 4 | What were Apple's total net sales in fiscal 2025? | $416,161 million | 4 | 1 |
| 5 | What was JPMorgan Chase's net income in 2024? | $58,471 million | 2 | 2 |
| 6 | What was JPMorgan Chase's CET1 capital ratio at the end of 2024? | 15.7% (Standardized) | 1 | 1 |
| 7 | What were JPMorgan Chase's total assets in 2025? | $4,424,900 million | 5 | 7 |
| 8 | What was NVIDIA's Data Center revenue in fiscal 2025? | $115,186 million | 2 | 3 |
| 9 | What was NVIDIA's revenue in fiscal 2026? | $215,938 million | 5 | 2 |

## Change over time

| # | Question | Expected answer | Hybrid | + Reranker |
|---|---|---|---:|---:|
| 10 | How did Apple's total net sales change from 2022 to 2023? | Down from $394,328 million to $383,285 million (−3%) | 1 | 2 |

## Multi-document comparison

| # | Question | Expected answer | Hybrid | + Reranker |
|---|---|---|---:|---:|
| 11 | How many full-time employees did Apple and Microsoft each have in 2025? | Apple ~166,000; Microsoft ~228,000 | 4 / 7 | 2 / 1 |
| 12 | Compare Apple's fiscal 2025 net income with NVIDIA's fiscal 2026 net income. | Apple $112,010 million vs NVIDIA $120,067 million | 4 / 7 | 7 / 2 |

For comparisons the ranks are per company (first / second). Question 12 is not in the benchmark file; its ranks come from a one-off check with the same retrieval code.

## Narrative / risk disclosures

| # | Question | Expected answer | Hybrid | + Reranker |
|---|---|---|---:|---:|
| 13 | What is Microsoft's relationship with OpenAI? | Long-term strategic partnership since 2019; Microsoft is a major investor, with reciprocal revenue sharing | 1 | 1 |
| 14 | How does JPMorgan Chase describe operational risk? | Risk from fraud, business disruption, cyber attacks, employee behaviour, compliance failures and third-party failures | 1 | 1 |
| 15 | How have U.S. export controls affected NVIDIA's ability to sell to China? | USG licensing requirements restrict exports of products such as the A100/H100 to China, harming its competitive position there | 3 | 2 |

## Grounded refusal

| Question | Expected behaviour |
|---|---|
| What was Tesla's total revenue in 2024? | The model says the sources are insufficient and cites nothing — Tesla is not in the corpus |

## Questions to avoid in a live demo

Retrieval currently misses these (see the benchmark), so the model correctly refuses — accurate, but not a good first impression:

- Microsoft net income / revenue by fiscal year (financial-statement tables in the DOCX filings are not retrieved)
- Apple balance-sheet line items for 2023 (cash, inventories, marketable securities), which lose out to near-identical tables from other years
- "Compare Apple's R&D expense in 2023 with Microsoft's R&D expense in fiscal 2024" — the Microsoft figure is missed in both modes

Filtering retrieval by the company and year named in the question is the planned fix.
