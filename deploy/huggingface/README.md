---
title: busiRAG
emoji: 📊
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Cited answers from company annual reports (RAG demo)
---

# busiRAG demo

Ask questions about Apple, Microsoft, NVIDIA and JPMorgan Chase annual reports and get answers with citations to the exact source passage.

This Space runs the [busiRAG](https://github.com/iamzimozic/busiRAG) API and frontend in one container. The documents were ingested ahead of time into a hosted PostgreSQL + pgvector database; only those documents are searchable, and the workspace is read-only.

Setup: see "Free deployment" in the repository's `DEPLOYMENT.md`.
