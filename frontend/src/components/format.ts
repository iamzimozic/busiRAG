export function formatMs(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)} ms`;
  }

  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`;
}

export function formatScore(score: number | null): string {
  if (score === null) {
    return "—";
  }

  // RRF scores are small (≈0.01–0.03); show enough precision to compare.
  return Math.abs(score) < 0.1 ? score.toFixed(4) : score.toFixed(3);
}

export function formatElementType(elementType: string | null): string | null {
  if (!elementType) {
    return null;
  }

  return elementType.charAt(0).toUpperCase() + elementType.slice(1);
}

const MODE_LABELS: Record<string, string> = {
  dense: "Dense",
  sparse: "Full-text",
  hybrid: "Hybrid (RRF)",
  hybrid_rerank: "Hybrid + reranker",
};

export function formatRetrievalMode(mode: string): string {
  return MODE_LABELS[mode] ?? mode;
}
