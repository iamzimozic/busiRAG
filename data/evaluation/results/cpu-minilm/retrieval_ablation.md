| Retrieval | Recall@5 | Recall@10 | MRR | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|
| Hybrid (RRF) | 0.500 | 0.562 | 0.295 | 47 ms | 55 ms |
| Hybrid + reranker | 0.412 | 0.588 | 0.326 | 5300 ms | 5748 ms |

Recall@10 by question type:

| Retrieval | comparison (n=3) | multi_period (n=3) | narrative (n=7) | table_numeric (n=27) |
|---|---:|---:|---:|---:|
| Hybrid (RRF) | 0.500 | 0.333 | 0.857 | 0.519 |
| Hybrid + reranker | 0.500 | 0.667 | 0.857 | 0.519 |

40 questions over 12 filings; top_k=10, candidate_k=50; embeddings `BAAI/bge-small-en-v1.5`, reranker `cross-encoder/ms-marco-MiniLM-L-6-v2`; latency measured on cpu (commit `788e9d1`).
