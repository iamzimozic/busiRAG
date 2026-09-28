| Retrieval | Recall@5 | Recall@10 | MRR | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|
| Dense (pgvector) | 0.375 | 0.588 | 0.259 | 30 ms | 45 ms |
| Sparse (Postgres FTS) | 0.225 | 0.275 | 0.146 | 2 ms | 4 ms |
| Hybrid (RRF) | 0.500 | 0.562 | 0.295 | 43 ms | 53 ms |
| Hybrid + reranker | 0.637 | 0.675 | 0.483 | 3736 ms | 5734 ms |

Recall@10 by question type:

| Retrieval | comparison (n=3) | multi_period (n=3) | narrative (n=7) | table_numeric (n=27) |
|---|---:|---:|---:|---:|
| Dense (pgvector) | 0.500 | 0.667 | 0.857 | 0.519 |
| Sparse (Postgres FTS) | 0.000 | 0.667 | 0.143 | 0.296 |
| Hybrid (RRF) | 0.500 | 0.333 | 0.857 | 0.519 |
| Hybrid + reranker | 0.667 | 1.000 | 0.857 | 0.593 |

40 questions over 12 filings; top_k=10, candidate_k=50; embeddings `BAAI/bge-small-en-v1.5`, reranker `BAAI/bge-reranker-v2-m3`; latency measured on NVIDIA GeForce RTX 3060 Laptop GPU (commit `e00dfb4`).
